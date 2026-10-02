"""Preparation and launcher tests with fake files/processes only."""
import copy
import gzip
import hashlib
import json
from pathlib import Path
import signal
import subprocess
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import prepare_replay as prepare
from portable_runtime import BindingError, sha
from test_portable_runtime import Fixture, TemporaryTests


class ReleaseTests(TemporaryTests):
    def setUp(self):
        super().setUp()
        self.package = self.root / 'package'; self.package.mkdir()
        self.source = self.package / 'core.py'; self.source.write_text('source bytes\n')
        self.manifest = {'files': {'core.py': sha(self.source)}, 'external_files': {}}
        self.manifest_path = self.package / 'PACKAGE_MANIFEST.json'
        self.manifest_path.write_text(json.dumps(self.manifest))
        self.package_patch = patch.object(prepare, 'PACKAGE', self.package)
        self.package_patch.start(); self.addCleanup(self.package_patch.stop)

    def test_exact_release_files_and_hashes_accepted(self):
        self.assertEqual(prepare.release(), self.manifest)

    def test_missing_extra_and_bytecode_release_files_rejected(self):
        for name in ('unlisted.py', 'unlisted.pyc', '__pycache__/core.pyc', 'dangling'):
            extra = self.package / name; extra.parent.mkdir(parents=True, exist_ok=True)
            if name == 'dangling': extra.symlink_to(self.root / 'absent')
            else: extra.write_text('unlisted')
            with self.subTest(name=name), self.assertRaisesRegex(BindingError, 'missing or unexpected'):
                prepare.release()
            extra.unlink()
        self.source.unlink()
        with self.assertRaisesRegex(BindingError, 'missing or unexpected'): prepare.release()

    def test_changed_release_bytes_rejected(self):
        self.source.write_text('different bytes\n')
        with self.assertRaisesRegex(BindingError, 'Pinned artifact changed'): prepare.release()

    def test_source_release_symlink_escape_rejected(self):
        external = self.root / 'external.py'; external.write_text('source bytes\n')
        self.source.unlink(); self.source.symlink_to(external)
        with self.assertRaisesRegex(BindingError, 'escapes root'): prepare.release()


class SourceInventoryTests(TemporaryTests):
    def setUp(self):
        super().setUp()
        self.package = self.root / 'package'; self.package.mkdir()
        self.source = self.root / 'source'; self.source.mkdir()
        self.entries = []
        for index in range(983):
            name = 'source_%04d.txt' % index
            path = self.source / name; path.write_text('source ' + str(index))
            self.entries.append(sha(path) + '  ' + name)
        self.inventory = self.package / 'SOURCE_TREE.sha256'
        self.inventory.write_text('\n'.join(self.entries) + '\n')
        self.package_patch = patch.object(prepare, 'PACKAGE', self.package)
        self.package_patch.start(); self.addCleanup(self.package_patch.stop)

    def test_exact_source_inventory_and_excluded_git_metadata(self):
        git = self.source / '.git'; git.mkdir(); (git / 'config').write_text('fake metadata')
        receipt = prepare.source_inventory(self.source)
        self.assertEqual(receipt['source_files'], 983)
        self.assertTrue(receipt['exact_tree_verified'])
        self.assertEqual(receipt['base_commit'], prepare.PIN)

    def test_extra_missing_and_altered_source_rejected(self):
        extra = self.source / 'extra.txt'; extra.write_text('extra')
        with self.assertRaisesRegex(BindingError, 'extra or missing'): prepare.source_inventory(self.source)
        extra.unlink()
        first = self.source / 'source_0000.txt'; first.unlink()
        with self.assertRaisesRegex(BindingError, 'extra or missing'): prepare.source_inventory(self.source)
        first.write_text('changed')
        with self.assertRaisesRegex(BindingError, 'Pinned artifact changed'): prepare.source_inventory(self.source)

    def test_duplicate_incomplete_and_traversal_inventory_rejected(self):
        for entries, error in ((self.entries + [self.entries[0]], 'Duplicate'),
                               (self.entries[:-1], 'Incomplete'),
                               (self.entries[:-1] + ['a' * 64 + '  ../escape.py'], 'extra or missing')):
            self.inventory.write_text('\n'.join(entries) + '\n')
            with self.subTest(error=error), self.assertRaisesRegex(BindingError, error):
                prepare.source_inventory(self.source)


class BuildIdentityTests(TemporaryTests):
    def setUp(self):
        super().setUp()
        self.source = self.root / 'source'; self.source.mkdir()
        self.build = self.root / 'build'; self.build.mkdir()
        (self.build / 'bin').mkdir(); (self.build / 'bin/highs').write_text('fake binary')
        (self.build / 'lib').mkdir()
        self.library = self.build / 'lib/libhighs.so.1.0'; self.library.write_text('fake main DSO')
        (self.build / 'lib/libhighs.so').symlink_to(self.library.name)
        (self.build / 'lib/libhighs.so.1').symlink_to(self.library.name)
        (self.build / 'lib/libhighs_extras.so').write_text('fake extras DSO')
        self.header = self.build / 'HConfig.h'
        self.header_text = '#define FAST_BUILD\n#define CMAKE_BUILD_TYPE "Release"\n/* #undef HIGHSINT64 */\n'
        self.header.write_text(self.header_text)
        self.compiler = self.build / 'CMakeFiles/mock/CMakeCXXCompiler.cmake'
        self.compiler.parent.mkdir(parents=True); self.compiler.write_text('# fake compiler metadata\n')
        self.fields = {'CMAKE_BUILD_TYPE': 'Release', 'FAST_BUILD': 'ON', 'BUILD_SHARED_LIBS': 'ON',
                       'HIPO': 'OFF', 'HIGHSINT64': 'OFF', 'BUILD_TESTING': 'ON', 'ALL_TESTS': 'ON',
                       'CMAKE_C_FLAGS': '', 'CMAKE_CXX_FLAGS': '',
                       'CMAKE_C_FLAGS_RELEASE': '-O3 -DNDEBUG', 'CMAKE_CXX_FLAGS_RELEASE': '-O3 -DNDEBUG',
                       'CMAKE_HOME_DIRECTORY': str(self.source), 'CMAKE_CXX_COMPILER': '/mock/c++'}
        self.cache = self.build / 'CMakeCache.txt'; self.save_fields(self.fields)

    def save_fields(self, fields):
        self.cache.write_text('\n'.join(k + ':STRING=' + v for k, v in fields.items()) + '\n')

    def test_exact_flags_header_aliases_and_compiler_metadata_accepted(self):
        record = prepare.build_identity(self.source, self.build)
        self.assertEqual(record['library'], str(self.library))
        self.assertEqual(record['compiler']['CMAKE_CXX_COMPILER'], '/mock/c++')
        self.assertIn(str(self.compiler), record['build_pins'])
        self.assertEqual(record['aliases'][str(self.build / 'lib/libhighs.so.1')], str(self.library))

    def test_each_required_flag_must_exist_and_match(self):
        for key in ('CMAKE_BUILD_TYPE', 'FAST_BUILD', 'BUILD_SHARED_LIBS', 'HIPO', 'HIGHSINT64', 'BUILD_TESTING', 'ALL_TESTS',
                    'CMAKE_C_FLAGS', 'CMAKE_CXX_FLAGS', 'CMAKE_C_FLAGS_RELEASE', 'CMAKE_CXX_FLAGS_RELEASE'):
            for mode in ('missing', 'changed'):
                fields = dict(self.fields)
                if mode == 'missing': del fields[key]
                else: fields[key] = 'unexpected'
                self.save_fields(fields)
                with self.subTest(key=key, mode=mode), self.assertRaisesRegex(BindingError, 'Build flags'):
                    prepare.build_identity(self.source, self.build)

    def test_wrong_source_or_int64_header_rejected(self):
        fields = dict(self.fields, CMAKE_HOME_DIRECTORY=str(self.root / 'other'))
        self.save_fields(fields)
        with self.assertRaisesRegex(BindingError, 'source directory mismatch'):
            prepare.build_identity(self.source, self.build)
        self.save_fields(self.fields)
        for header in ('#define HIGHSINT64\n', '  # define HIGHSINT64 1\n'):
            self.header.write_text(self.header_text + header)
            with self.subTest(header=header), self.assertRaisesRegex(BindingError, '64-bit HighsInt'):
                prepare.build_identity(self.source, self.build)

    def test_hardened_build_header_requires_release_fast_build_without_hipo(self):
        for header in ('#define CMAKE_BUILD_TYPE "Release"\n', '#define FAST_BUILD\n',
                       '#define FAST_BUILD\n#define CMAKE_BUILD_TYPE "Debug"\n',
                       self.header_text + '#define HIPO\n'):
            self.header.write_text(header)
            with self.subTest(header=header), self.assertRaises(BindingError):
                prepare.build_identity(self.source, self.build)

    def test_linker_toolchain_launcher_and_lto_overrides_rejected(self):
        forbidden = {key: '-Wl,--unreviewed' for key in (
            'CMAKE_EXE_LINKER_FLAGS', 'CMAKE_SHARED_LINKER_FLAGS', 'CMAKE_MODULE_LINKER_FLAGS',
            'CMAKE_EXE_LINKER_FLAGS_RELEASE', 'CMAKE_SHARED_LINKER_FLAGS_RELEASE', 'CMAKE_MODULE_LINKER_FLAGS_RELEASE')}
        forbidden.update({'CMAKE_TOOLCHAIN_FILE': '/mock/toolchain.cmake', 'CMAKE_C_COMPILER_LAUNCHER': '/mock/launcher',
                          'CMAKE_CXX_COMPILER_LAUNCHER': '/mock/launcher',
                          'CMAKE_INTERPROCEDURAL_OPTIMIZATION': 'ON', 'CMAKE_INTERPROCEDURAL_OPTIMIZATION_RELEASE': 'ON'})
        for key, value in forbidden.items():
            self.save_fields({**self.fields, key: value})
            with self.subTest(key=key), self.assertRaises(BindingError):
                prepare.build_identity(self.source, self.build)

    def test_binary_symlink_cannot_escape_build_directory(self):
        foreign = self.root / 'foreign-highs'; foreign.write_text('outside executable')
        binary = self.build / 'bin/highs'; binary.unlink(); binary.symlink_to(foreign)
        with self.assertRaises(BindingError): prepare.build_identity(self.source, self.build)

    def test_soname_and_compiler_metadata_required(self):
        alias = self.build / 'lib/libhighs.so.1'; alias.unlink()
        with self.assertRaisesRegex(BindingError, 'SONAME'): prepare.build_identity(self.source, self.build)
        alias.symlink_to(self.library.name); self.compiler.unlink()
        with self.assertRaisesRegex(BindingError, 'Compiler metadata'): prepare.build_identity(self.source, self.build)

    def test_foreign_library_alias_rejected(self):
        foreign = self.root / 'foreign.so'; foreign.write_text('foreign')
        alias = self.build / 'lib/libhighs.so.1'; alias.unlink(); alias.symlink_to(foreign)
        with self.assertRaisesRegex(BindingError, 'alias target'):
            prepare.build_identity(self.source, self.build)


class DataBindingTests(TemporaryTests):
    def setUp(self):
        super().setUp()
        self.data = self.root / 'data'; self.data.mkdir()
        self.manifest = {'data': {}}
        self.files = []
        for date in prepare.DATES:
            raw = ('fake data for ' + date).encode()
            path = self.data / ('case89pegase_' + date + '.json.gz')
            path.write_bytes(gzip.compress(raw, mtime=0)); self.files.append(path)
            self.manifest['data'][date] = {
                'compressed_sha256': sha(path), 'decompressed_sha256': hashlib.sha256(raw).hexdigest(),
            }

    def test_exact_compressed_and_decompressed_hashes_all_dates(self):
        self.assertEqual(prepare.verify_data(self.data, self.manifest), {str(path): sha(path) for path in self.files})

    def test_each_hash_required(self):
        for date in prepare.DATES:
            for field, error in (('compressed_sha256', 'Compressed'), ('decompressed_sha256', 'Decompressed')):
                manifest = copy.deepcopy(self.manifest); manifest['data'][date][field] = '0' * 64
                with self.subTest(date=date, field=field), self.assertRaisesRegex(BindingError, error):
                    prepare.verify_data(self.data, manifest)

    def test_data_symlink_escape_rejected_even_with_same_bytes(self):
        first = self.files[0]; external = self.root / 'external.json.gz'
        external.write_bytes(first.read_bytes()); first.unlink(); first.symlink_to(external)
        with self.assertRaisesRegex(BindingError, 'escapes data directory'):
            prepare.verify_data(self.data, self.manifest)


def proc_stat(pid, parent, start):
    return str(pid) + ' (mock worker (name)) ' + ' '.join(['S', str(parent)] + ['0'] * 17 + [str(start)])


class CancellationTests(unittest.TestCase):
    def test_cancellation_signals_enter_existing_cleanup_path(self):
        for signum in (signal.SIGTERM, signal.SIGHUP, signal.SIGINT):
            with self.subTest(signum=signum), self.assertRaises(KeyboardInterrupt):
                prepare.cancellation_signal(signum, None)

    def test_descendants_match_parent_chain_and_start_identity(self):
        entries = [Path('/proc') / str(pid) for pid in (100, 101, 102, 103, 200, 300)] + [Path('/proc/self')]
        records = {100: proc_stat(100, 1, '1000'), 101: proc_stat(101, 100, '1010'),
                   102: proc_stat(102, 101, '1020'), 103: 'malformed',
                   200: proc_stat(200, 1, '2000'), 300: proc_stat(300, 200, '3000')}
        def read(path, *args, **kwargs): return records[int(path.parent.name)]
        with patch.object(Path, 'iterdir', return_value=iter(entries)), patch.object(Path, 'read_text', read):
            self.assertEqual(prepare.descendant_identities(100), {101: '1010', 102: '1020'})

    def test_kill_checks_current_start_time_and_ignores_disappeared_pids(self):
        def read(path, *args, **kwargs):
            pid = int(path.parent.name)
            if pid == 103: raise FileNotFoundError('disappeared')
            if pid == 104: return 'malformed'
            return proc_stat(pid, 100, '1010' if pid == 101 else 'reused-new-start')
        with patch.object(Path, 'read_text', read), patch.object(prepare.os, 'kill') as kill:
            prepare.kill_identified_descendants({101: '1010', 102: '1020', 103: '1030', 104: '1040'})
        kill.assert_called_once_with(101, signal.SIGKILL)

    def test_bounded_timeout_kills_group_and_reaps_mock_process(self):
        process = Mock(pid=900)
        timeout = subprocess.TimeoutExpired(['mock'], 2)
        process.communicate.side_effect = [timeout, ('', '')]
        with patch.object(prepare.subprocess, 'Popen', return_value=process) as popen, patch.object(prepare.os, 'killpg') as kill:
            with self.assertRaises(subprocess.TimeoutExpired):
                prepare.bounded(['mock', 'argument with space'], env={'PATH': '/mock'}, cwd='/mock/work', timeout=2)
        kill.assert_called_once_with(900, signal.SIGKILL)
        self.assertEqual(process.communicate.call_count, 2)
        self.assertEqual(popen.call_args.args[0], ['mock', 'argument with space'])
        self.assertEqual(popen.call_args.kwargs['env'], {'PATH': '/mock'})
        self.assertTrue(popen.call_args.kwargs['start_new_session'])
        self.assertNotIn('shell', popen.call_args.kwargs)


class LauncherTests(TemporaryTests):
    def test_cancelled_driver_grace_then_kills_recorded_descendants_and_reaps(self):
        fixture = Fixture(self.root)
        process = Mock(pid=900)
        process.wait.side_effect = [KeyboardInterrupt(), subprocess.TimeoutExpired(['mock-driver'], 10), -9]
        descendants = {901: 'one', 902: 'two'}
        with patch.object(prepare, 'PACKAGE', fixture.package), patch.object(prepare, 'release'), \
             patch.object(prepare, 'source_inventory'), patch.object(prepare.subprocess, 'Popen', return_value=process), \
             patch.object(prepare, 'descendant_identities', return_value=descendants) as identify, \
             patch.object(prepare, 'kill_identified_descendants') as kill_identified, patch.object(prepare.os, 'killpg') as kill_group:
            with self.assertRaises(KeyboardInterrupt):
                prepare.run(SimpleNamespace(work=str(fixture.work), phase='tiny'))
        identify.assert_called_once_with(900)
        process.send_signal.assert_called_once_with(signal.SIGINT)
        kill_identified.assert_called_once_with(descendants)
        kill_group.assert_called_once_with(900, signal.SIGKILL)
        self.assertEqual(process.wait.call_count, 3)
        receipt = json.loads((fixture.work / 'tiny.launch_receipt.json').read_text())
        self.assertEqual(receipt['status'], 'failed_or_cancelled')
        self.assertIn('KeyboardInterrupt', receipt['error'])
        self.assertTrue((fixture.work / 'tiny.launch.started.json').exists())

    def test_existing_phase_marker_prevents_process_launch(self):
        fixture = Fixture(self.root)
        (fixture.work / 'tiny.launch.started.json').write_text('{}')
        with patch.object(prepare, 'PACKAGE', fixture.package), patch.object(prepare, 'release'), \
             patch.object(prepare, 'source_inventory'), patch.object(prepare.subprocess, 'Popen') as popen:
            with self.assertRaises(BindingError): prepare.run(SimpleNamespace(work=str(fixture.work), phase='tiny'))
        popen.assert_not_called()


class SourceSyntaxTests(unittest.TestCase):
    def test_all_package_python_source_compiles_without_execution(self):
        root = Path(__file__).resolve().parent.parent
        sources = sorted(root.rglob('*.py'))
        self.assertTrue(sources)
        for path in sources:
            with self.subTest(source=str(path.relative_to(root))):
                compile(path.read_bytes(), str(path), 'exec', dont_inherit=True)


if __name__ == '__main__':
    unittest.main(verbosity=2)
