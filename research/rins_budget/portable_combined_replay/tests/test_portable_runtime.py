"""Standard-library-only portable binding tests; all runtime artifacts are fake."""
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import portable_runtime as runtime


class Fixture:
    """A self-contained materialization with independently enumerated pins."""
    def __init__(self, root):
        self.root = Path(root)
        self.package = self.root / 'package'
        self.work = self.root / 'work'
        self.here = self.work / 'replay/combined_screening_driver'
        self.research = self.root / 'research'
        self.data = self.root / 'data'
        for directory in (self.package, self.here, self.research, self.data,
                          self.root / 'source', self.root / 'build', self.root / 'startup'):
            directory.mkdir(parents=True)
        self.release_file = self.put('package/payload/combined_screening_driver/core.py', 'core bytes\n')
        self.staged_file = self.put('work/replay/combined_screening_driver/core.py', 'core bytes\n')
        self.external_file = self.put('research/scuc/generate.py', 'external bytes\n')
        self.staged_external = self.put('work/replay/scuc/generate.py', 'external bytes\n')
        self.prepared_file = self.put('source/header.h', 'source inventory witness\n')
        self.runtime_file = self.put('build/native-runtime.so', 'mock ELF bytes\n')
        self.loader_file = self.put('build/native-loader.so', 'mock loader dependency\n')
        self.binary = self.put('build/highs', 'mock executable\n')
        self.library = self.put('build/libhighs.so', 'mock main DSO\n')
        self.extras = self.put('build/libhighs_extras.so', 'mock extras DSO\n')
        self.plan = self.put('work/replay/combined_screening_driver/CAMPAIGN_PLAN.json', '{}\n')
        self.data_files = [self.put('data/case89pegase_' + date + '.json.gz', date + '\n')
                           for date in runtime.DATES]
        self.release = {
            'files': {'payload/combined_screening_driver/core.py': runtime.sha(self.release_file)},
            'external_files': {'scuc/generate.py': runtime.sha(self.external_file)},
            'external_materialization': {'scuc/generate.py': 'scuc/generate.py'},
            'data': {date: {'compressed_sha256': runtime.sha(path)}
                     for date, path in zip(runtime.DATES, self.data_files)},
        }
        self.release_path = self.put_json('package/PACKAGE_MANIFEST.json', self.release)
        self.value = {
            'schema': 1, 'driver': str(self.here), 'work': str(self.work),
            'source': str(self.root / 'source'), 'build': str(self.root / 'build'),
            'data': str(self.data), 'package': str(self.package), 'research_package': str(self.research),
            'python': sys.executable, 'binary': str(self.binary), 'library': str(self.library),
            'extras': str(self.extras), 'release_sha256': runtime.sha(self.release_path),
            'preparation_pins': {str(self.prepared_file): runtime.sha(self.prepared_file)},
            'campaign_plan_sha256': runtime.sha(self.plan),
            'python_inspection': {'startup_directories': [str(self.root / 'startup')]},
        }
        self.binding_path = self.put_json('work/replay/combined_screening_driver/BINDINGS.json', self.value)
        self.inventory = {'artifact_sha256': {str(self.runtime_file): runtime.sha(self.runtime_file)}}
        self.inventory_path = self.put_json('work/runtime_inventory.json', self.inventory)
        self.loader_inventory = {'artifact_sha256': {str(self.loader_file): runtime.sha(self.loader_file)}}
        self.loader_inventory_path = self.put_json('work/loader_inventory.json', self.loader_inventory)
        self.mandatory_paths = [self.release_path, self.release_file, self.staged_file,
                                self.external_file, self.staged_external, *self.data_files,
                                self.prepared_file, self.binding_path, self.plan,
                                self.runtime_file, self.inventory_path, self.loader_file, self.loader_inventory_path]
        self.record = {
            'status': runtime.STATUS, 'release_sha256': runtime.sha(self.release_path),
            'bindings_sha256': runtime.sha(self.binding_path),
            'runtime_inventory_sha256': runtime.sha(self.inventory_path),
            'loader_inventory_sha256': runtime.sha(self.loader_inventory_path),
            'artifact_sha256': {str(path): runtime.sha(path) for path in self.mandatory_paths},
        }
        self.record_path = self.put_json('work/replay/combined_screening_driver/REVIEW_MANIFEST.json', self.record)

    def put(self, relative, contents):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents)
        return path

    def put_json(self, relative, value):
        return self.put(relative, json.dumps(value, allow_nan=False) + '\n')

    def save_record(self, record):
        self.record_path.write_text(json.dumps(record, allow_nan=False))


class TemporaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)


class PathTests(TemporaryTests):
    def test_controls_empty_and_nonstring_paths_rejected(self):
        for value in ('', None, 1, *('bad' + chr(i) + 'path' for i in (*range(32), 127))):
            with self.subTest(value=repr(value)), self.assertRaises(runtime.BindingError):
                runtime.checked_path(value, exists=False)

    def test_ordinary_spaces_allowed_except_loader_paths(self):
        path = self.root / 'data and output'
        path.mkdir()
        self.assertEqual(runtime.checked_path(str(path)), path)
        for name in ('with space', 'with\u00a0space', 'with:colon'):
            with self.subTest(name=name), self.assertRaises(runtime.BindingError):
                runtime.checked_path(str(self.root / name), exists=False, library=True)
        link = self.root / 'loader'
        link.symlink_to(path, target_is_directory=True)
        with self.assertRaises(runtime.BindingError):
            runtime.checked_path(str(link), library=True)

    def test_relative_traversal_absolute_controls_and_symlink_escape_rejected(self):
        source = self.root / 'source'; source.mkdir()
        (source / 'safe.py').write_text('safe')
        outside = self.root / 'outside.py'; outside.write_text('outside')
        (source / 'escape.py').symlink_to(outside)
        for name in ('', '.', '..', '../outside.py', 'sub/../../outside.py', str(outside), 'escape.py', 'bad\n.py'):
            with self.subTest(name=name), self.assertRaises(runtime.BindingError):
                runtime.relative_path(source, name)
        self.assertEqual(runtime.relative_path(source, 'safe.py'), source / 'safe.py')

    def test_fresh_output_refuses_existing_file_directory_and_dangling_symlink(self):
        directory = self.root / 'directory'; directory.mkdir()
        regular = self.root / 'file'; regular.write_text('unchanged')
        link = self.root / 'dangling'; link.symlink_to(self.root / 'missing')
        for path in (directory, regular, link):
            with self.subTest(path=path), self.assertRaises(runtime.BindingError):
                runtime.fresh_directory(path)
        self.assertEqual(regular.read_text(), 'unchanged')
        self.assertTrue(link.is_symlink())

    def test_fresh_output_rejects_protected_overlap_and_missing_parent(self):
        protected = self.root / 'protected'; protected.mkdir()
        for output, protected_paths in ((protected / 'child', (protected,)),
                                        (self.root / 'ancestor', (self.root / 'ancestor/nested',)),
                                        (self.root / 'missing/child', ())):
            with self.subTest(output=output), self.assertRaises(runtime.BindingError):
                runtime.fresh_directory(output, protected_paths)
            self.assertFalse(output.exists())
        link = self.root / 'input-link'; link.symlink_to(protected, target_is_directory=True)
        with self.assertRaises(runtime.BindingError):
            runtime.fresh_directory(link / 'output', (protected,))
        fresh = runtime.fresh_directory(self.root / 'fresh output', (protected,))
        self.assertTrue(fresh.is_dir())
        self.assertEqual(list(fresh.iterdir()), [])


class JsonTests(TemporaryTests):
    def test_duplicate_and_nonfinite_json_rejected_at_any_depth(self):
        path = self.root / 'record.json'
        for encoded in ('{"x":1,"x":2}', '{"nested":{"x":1,"x":2}}',
                        '{"x":NaN}', '[Infinity]', '{"nested":[-Infinity]}',
                        '{"nested":[1e999]}', '{"nested":{"negative":-1e999}}'):
            path.write_text(encoded)
            with self.subTest(encoded=encoded), self.assertRaises(runtime.BindingError):
                runtime.read_json(path)
        path.write_text('{"x":[1,2.5],"yes":true}')
        self.assertEqual(runtime.read_json(path), {'x': [1, 2.5], 'yes': True})

    def test_json_writer_is_exclusive_and_refuses_nonfinite_values(self):
        path = self.root / 'new.json'
        runtime.write_json(path, {'x': 1})
        self.assertEqual(runtime.read_json(path), {'x': 1})
        with self.assertRaises(runtime.BindingError): runtime.write_json(path, {'x': 2})
        self.assertEqual(runtime.read_json(path), {'x': 1})
        link = self.root / 'dangling.json'; link.symlink_to(self.root / 'absent.json')
        with self.assertRaises(runtime.BindingError): runtime.write_json(link, {})
        for index, value in enumerate((float('nan'), float('inf'), -float('inf'))):
            with self.subTest(value=value), self.assertRaises(ValueError):
                runtime.write_json(self.root / ('nonfinite_' + str(index)), {'value': value})


class BindingTests(TemporaryTests):
    def test_unprepared_import_and_runtime_rejection(self):
        self.assertIsNone(runtime.bindings(self.root))
        with self.assertRaisesRegex(runtime.BindingError, 'prepare'):
            runtime.validate_manifest(self.root)

    def test_relocated_or_wrong_schema_bindings_rejected(self):
        fixture = Fixture(self.root)
        self.assertEqual(runtime.bindings(fixture.here), fixture.value)
        for key, value in (('driver', str(self.root / 'relocated')), ('schema', 2)):
            bad = dict(fixture.value); bad[key] = value
            fixture.binding_path.write_text(json.dumps(bad))
            with self.subTest(key=key), self.assertRaisesRegex(runtime.BindingError, 'relocated'):
                runtime.bindings(fixture.here)

    def test_environment_is_fixed_and_does_not_inherit_parent_injection(self):
        fixture = Fixture(self.root)
        injected = {'LD_PRELOAD': '/host/inject.so', 'LD_AUDIT': '/host/audit.so',
                    'PYTHONPATH': '/host/python', 'PYTHONHOME': '/host/home', 'PYTHONOPTIMIZE': '2',
                    'AWS_SECRET_ACCESS_KEY': 'test-only-secret', 'HTTPS_PROXY': 'https://example.invalid',
                    'HOME': '/host/user', 'PATH': '/host/bin', 'OPENBLAS_NUM_THREADS': '88'}
        with patch.dict(os.environ, injected, clear=True):
            environment = runtime.minimal_environment(fixture.here)
        self.assertEqual(environment, {
            'PATH': '/usr/bin:/bin', 'LANG': 'C', 'LC_ALL': 'C', 'TZ': 'UTC',
            'HOME': str(fixture.work / 'environment/home'), 'TMPDIR': str(fixture.work / 'environment/tmp'),
            'XDG_CACHE_HOME': str(fixture.work / 'environment/cache'),
            'OPENBLAS_NUM_THREADS': '1', 'OMP_NUM_THREADS': '1', 'MKL_NUM_THREADS': '1',
            'NUMEXPR_NUM_THREADS': '1', 'PYTHONHASHSEED': '0', 'PYTHONDONTWRITEBYTECODE': '1',
            'PYTHONNOUSERSITE': '1', 'LD_LIBRARY_PATH': str(fixture.library.parent),
        })
        self.assertNotIn('test-only-secret', environment.values())

    def test_unprepared_environment_cannot_point_at_parent_library(self):
        with patch.dict(os.environ, {'LD_LIBRARY_PATH': '/host/lib'}, clear=True):
            environment = runtime.minimal_environment(self.root / 'driver')
        self.assertEqual(environment['LD_LIBRARY_PATH'], str(self.root / 'UNPREPARED/lib'))


class PinTests(TemporaryTests):
    def test_release_pins_include_package_copy_external_copy_and_all_dates(self):
        fixture = Fixture(self.root)
        expected = [fixture.release_path, fixture.release_file, fixture.staged_file,
                    fixture.external_file, fixture.staged_external, *fixture.data_files]
        pins = runtime.release_pins(fixture.value)
        self.assertEqual(pins, {str(path): runtime.sha(path) for path in expected})
        runtime.verify(pins)

    def test_altered_release_manifest_rejected_before_adopting_new_pins(self):
        fixture = Fixture(self.root)
        release = copy.deepcopy(fixture.release)
        release['files']['payload/combined_screening_driver/core.py'] = '0' * 64
        fixture.release_path.write_text(json.dumps(release))
        with self.assertRaisesRegex(runtime.BindingError, 'Release manifest changed'):
            runtime.release_pins(fixture.value)

    def test_missing_or_altered_release_artifacts_rejected(self):
        fixture = Fixture(self.root)
        pins = runtime.release_pins(fixture.value)
        for path in (fixture.release_file, fixture.staged_file, fixture.external_file,
                     fixture.staged_external, *fixture.data_files):
            old = path.read_bytes()
            path.write_bytes(old + b'changed')
            with self.subTest(path=path, mode='altered'), self.assertRaises(runtime.BindingError):
                runtime.verify(pins)
            path.unlink()
            with self.subTest(path=path, mode='missing'), self.assertRaises(OSError):
                runtime.verify(pins)
            path.write_bytes(old)

    def test_release_source_escape_and_malformed_digest_rejected(self):
        fixture = Fixture(self.root)
        release = copy.deepcopy(fixture.release)
        release['files'] = {'../escape.py': '0' * 64}
        fixture.release_path.write_text(json.dumps(release))
        bound = dict(fixture.value, release_sha256=runtime.sha(fixture.release_path))
        with self.assertRaises(runtime.BindingError): runtime.release_pins(bound)
        for digest in ('', 'f' * 63, 'F' * 64, 'z' * 64):
            with self.subTest(digest=digest), self.assertRaises(runtime.BindingError):
                runtime.verify({str(fixture.release_file): digest})


class ManifestTests(TemporaryTests):
    def test_complete_manifest_passes(self):
        fixture = Fixture(self.root)
        self.assertEqual(runtime.validate_manifest(fixture.here), fixture.record)

    def test_each_mandatory_pin_cannot_be_omitted_changed_or_added(self):
        fixture = Fixture(self.root)
        for name in fixture.record['artifact_sha256']:
            for operation in ('remove', 'change'):
                record = copy.deepcopy(fixture.record)
                if operation == 'remove': del record['artifact_sha256'][name]
                else: record['artifact_sha256'][name] = '0' * 64
                fixture.save_record(record)
                with self.subTest(path=name, operation=operation), self.assertRaisesRegex(runtime.BindingError, 'Mandatory'):
                    runtime.validate_manifest(fixture.here)
        record = copy.deepcopy(fixture.record)
        record['artifact_sha256'][str(self.root / 'unrequested')] = '0' * 64
        fixture.save_record(record)
        with self.assertRaisesRegex(runtime.BindingError, 'Mandatory'):
            runtime.validate_manifest(fixture.here)

    def test_runtime_status_release_and_binding_hash_must_match(self):
        fixture = Fixture(self.root)
        for key, value in (('status', 'ready'), ('release_sha256', '0' * 64), ('bindings_sha256', '0' * 64)):
            record = dict(fixture.record); record[key] = value; fixture.save_record(record)
            with self.subTest(key=key), self.assertRaises(runtime.BindingError):
                runtime.validate_manifest(fixture.here)

    def test_changed_inventory_bindings_or_campaign_plan_rejected(self):
        fixture = Fixture(self.root)
        for path in (fixture.inventory_path, fixture.loader_inventory_path, fixture.binding_path,
                     fixture.plan, fixture.runtime_file, fixture.loader_file):
            old = path.read_bytes(); path.write_bytes(old + b' ')
            with self.subTest(path=path), self.assertRaises(runtime.BindingError):
                runtime.validate_manifest(fixture.here)
            path.write_bytes(old)

    def test_wrong_interpreter_rejected(self):
        fixture = Fixture(self.root)
        with patch.object(runtime.sys, 'executable', str(self.root / 'other-python')):
            with self.assertRaisesRegex(runtime.BindingError, 'Wrong interpreter'):
                runtime.validate_manifest(fixture.here)


class StartupTests(TemporaryTests):
    def test_unlisted_materialized_sources_and_symlinks_rejected(self):
        fixture = Fixture(self.root)
        extra = fixture.here / 'unexpected.py'; extra.write_text('unlisted source')
        with self.assertRaisesRegex(runtime.BindingError, 'Unlisted materialized source'):
            runtime.assert_clean_bundle(fixture.here, fixture.value)
        extra.unlink()
        original = fixture.staged_file.read_bytes()
        fixture.staged_file.unlink(); fixture.staged_file.symlink_to(fixture.release_file)
        with self.assertRaisesRegex(runtime.BindingError, 'Symlink in materialized replay'):
            runtime.assert_clean_bundle(fixture.here, fixture.value)
        fixture.staged_file.unlink(); fixture.staged_file.write_bytes(original)
        result = fixture.here / 'run_v1/tiny/result.json'
        result.parent.mkdir(parents=True); result.write_text('{}')
        runtime.assert_clean_bundle(fixture.here, fixture.value)

    def test_startup_hooks_rejected_without_execution(self):
        fixture = Fixture(self.root)
        runtime.assert_clean_bundle(fixture.here, fixture.value)
        marker = self.root / 'must-not-exist'
        for name in ('execute.pth', 'sitecustomize.py', 'sitecustomize.pyc', 'usercustomize.py', 'usercustomize.so'):
            hook = self.root / 'startup' / name
            hook.write_text('raise AssertionError("this hook must never execute")\n')
            with self.subTest(name=name), self.assertRaisesRegex(runtime.BindingError, 'Startup hook'):
                runtime.assert_clean_bundle(fixture.here, fixture.value)
            hook.unlink()
        self.assertFalse(marker.exists())

    def test_bundle_bytecode_caches_rejected_in_release_and_work(self):
        fixture = Fixture(self.root)
        for base in (fixture.package / 'payload', fixture.work / 'replay'):
            for name in ('stale.pyc', 'stale.pyo', '__pycache__'):
                artifact = base / name
                if name == '__pycache__': artifact.mkdir()
                else: artifact.write_bytes(b'not real bytecode')
                with self.subTest(base=base, name=name), self.assertRaisesRegex(runtime.BindingError, 'Bytecode cache'):
                    runtime.assert_clean_bundle(fixture.here, fixture.value)
                if artifact.is_dir(): artifact.rmdir()
                else: artifact.unlink()


if __name__ == '__main__':
    unittest.main(verbosity=2)
