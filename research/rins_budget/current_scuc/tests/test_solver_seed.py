"""Pure seed-plumbing regressions; every native/process boundary is mocked."""
import copy
from contextlib import ExitStack, contextmanager, nullcontext, redirect_stderr, redirect_stdout
import io
import json
import math
import os
from pathlib import Path
from types import MappingProxyType, SimpleNamespace
import tempfile
import unittest
from unittest.mock import Mock, patch

import numpy as np

from current_scuc import __main__ as cli
from current_scuc import binding, carry, case, common, heldout, options, preparation, process_runner
from current_scuc import native_exec, phase, seed
from current_scuc.science import capi


BAD_SEEDS = (True, False, 0.0, 1.0, math.nan, math.inf, -math.inf,
             -1, 2147483648, '1', None)
BAD_SPELLINGS = ('', '-1', '+1', '01', '00', '1.0', '1e0', 'nan', 'NaN',
                 'inf', ' 1', '1 ', '1\n', '１', '١', '2147483648', '9' * 100)


class SeedValidationTests(unittest.TestCase):
    def test_strict_python_values_and_canonical_decimal_boundaries(self):
        for value in (0, 1, 2, 2147483647):
            self.assertEqual(native_exec.validate_solver_random_seed(value), value)
            self.assertEqual(native_exec.parse_solver_random_seed(str(value)), value)
        for value in BAD_SEEDS:
            with self.subTest(value=value), self.assertRaises(ValueError):
                native_exec.validate_solver_random_seed(value)
        for value in (*BAD_SPELLINGS, True, 1, 1.0, None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                native_exec.parse_solver_random_seed(value)

    def test_cli_rejects_bad_seed_before_files_or_preparation(self):
        args = ['run', '--instance', '/unused/instance.json', '--highs', '/unused/highs',
                '--workdir', '/unused/output']
        with patch.object(process_runner, 'apply_limits'), \
                patch.object(binding, 'fresh_directory') as fresh, \
                patch.object(preparation, 'prepare') as prepare, \
                patch.object(process_runner, 'run') as run:
            for value in BAD_SPELLINGS:
                with self.subTest(value=value), redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit) as raised:
                        cli.main(args + ['--seed=' + value])
                    self.assertEqual(raised.exception.code, 2)
            fresh.assert_not_called()
            prepare.assert_not_called()
            run.assert_not_called()

    def test_native_argument_parser_uses_identical_canonical_seed_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            binary = root / 'highs'
            binary.write_text('placeholder, never executed')
            argv = options.command({'binary': binary}, root/'model.mps', root/'options',
                                   root/'solution', 120.)
            index = argv.index('--random_seed') + 1
            for value in (0, 1, 2, 2147483647):
                changed = list(argv)
                changed[index] = str(value)
                self.assertEqual(native_exec._validate_argv(changed, solver=True), binary)
            for value in BAD_SPELLINGS:
                changed = list(argv)
                changed[index] = value
                with self.subTest(value=value), self.assertRaises(ValueError):
                    native_exec._validate_argv(changed, solver=True)
            with self.assertRaises(ValueError):
                native_exec._validate_argv(argv + ['--random_seed', '1'], solver=True)

    def test_cli_default_zero_and_nonzero_seed_reach_arm_and_result(self):
        from current_scuc import case_binding, receipts, runtime
        summaries = []
        for flag, value in (([], 0), (['--seed', '0'], 0), (['--seed', '1'], 1), (['--seed', '2'], 2)):
            work = Path('/unused/work')
            candidate = dict(passed=False, result_complete=True, solver_random_seed=value,
                             outcome='mock_complete', whole_phase_seconds=1.)
            writes = {}
            with ExitStack() as stack:
                patches = (
                    patch.object(process_runner, 'apply_limits'),
                    patch.object(process_runner, 'run', return_value={'process_wall_seconds': 1.}),
                    patch.object(process_runner, 'require_clean'),
                    patch.object(binding, 'fresh_directory', return_value=work),
                    patch.object(binding, 'verify_package_source'),
                    patch.object(binding, 'sha', return_value='hash'),
                    patch.object(binding, 'config', return_value={'python': '/unused/python'}),
                    patch.object(binding, 'write', side_effect=lambda p, d, **k: writes.update({Path(p).name: copy.deepcopy(d)})),
                    patch.object(binding, 'read', side_effect=lambda p: candidate if Path(p).name == 'result.json'
                                 else {'result_sha256': 'hash', 'passed': False}),
                    patch.object(receipts, 'admit_cli', return_value={}),
                    patch.object(runtime, 'discover_runtime', return_value=SimpleNamespace(manifest_path=Path('/unused/runtime'))),
                    patch.object(preparation, 'prepare', return_value=Path('/unused/case')),
                    patch.object(case_binding, 'record', side_effect=lambda p: {'path': str(p), 'sha256': 'hash'}),
                    patch.object(case, 'bind_case'),
                    patch.object(case, 'create_source_reference', return_value=work/'reference.json'),
                    patch.object(cli.platform, 'system', return_value='Linux'),
                    patch.object(cli.platform, 'machine', return_value='x86_64'),
                    patch.dict(os.environ), redirect_stdout(io.StringIO()),
                )
                for item in patches:
                    stack.enter_context(item)
                arm = stack.enter_context(patch.object(case, 'create_arm_manifest', return_value=work/'arm.json'))
                status = cli.main(['run', '--instance', '/unused/instance', '--highs', '/unused/highs',
                                   '--workdir', str(work), *flag])
                self.assertEqual(status, 2)
                self.assertEqual(arm.call_args.kwargs, {'solver_random_seed': value})
            summary = writes['RESULT.json']
            self.assertEqual(summary['solver_random_seed'], value)
            self.assertTrue(summary['production_result'])
            self.assertEqual(summary['outcome'], 'mock_complete')
            summaries.append(summary)
        for name in ('solver_random_seed', 'passed', 'production_result', 'outcome', 'candidate_result'):
            self.assertEqual(summaries[0][name], summaries[1][name])

    def test_arm_manifest_defaults_and_selected_seed_are_typed_and_recorded(self):
        cb = case.cb
        record = lambda p: {'path': str(Path(p).resolve()), 'sha256': 'hash'}
        descriptor = dict(source=record('/unused/source'),
            model={'expected': record('/unused/expected'), 'mps': record('/unused/model')},
            case={'hours': 36}, shapes={'binary_count': 7},
            scope=dict(signed_normal_rows=2, signed_security_rows=4, unsigned_security_pair_hours=2),
            runtime={'config': {}})
        cfg = dict(source_manifest=record('/unused/freeze'), source_snapshot={}, library='/unused/lib.so',
                   runtime_pins={}, runtime_manifest='/unused/runtime', runtime_manifest_sha256='hash',
                   python='/unused/python')
        with patch.object(case, 'bind_case', return_value=descriptor), \
                patch.object(binding, 'verify_package_source'), \
                patch.object(binding, 'config', return_value=cfg), \
                patch.object(binding, 'verify_source_snapshot', return_value={'files_sha256': {}}), \
                patch.object(cb, 'record', side_effect=record), patch.object(cb, 'sha', return_value='hash'), \
                patch.object(cb, 'write') as write:
            manifests = []
            for kwargs in ({}, {'solver_random_seed': 0}, {'solver_random_seed': 1}, {'solver_random_seed': 2}):
                case.create_arm_manifest('/unused/case', '/unused/freeze', '/unused/arm', **kwargs)
                manifests.append(copy.deepcopy(write.call_args.args[1]))
            self.assertEqual(manifests[0], manifests[1])
            self.assertEqual([m['solver_random_seed'] for m in manifests], [0, 0, 1, 2])
            for manifest in manifests:
                self.assertIs(type(manifest['solver_random_seed']), int)

    def test_arm_and_heldout_reject_bad_seed_before_loading_case(self):
        with patch.object(case, 'bind_case') as bind, patch.object(heldout, 'case') as load:
            for value in BAD_SEEDS:
                with self.subTest(value=value):
                    with self.assertRaises(ValueError):
                        case.create_arm_manifest('/unused/case', '/unused/freeze', '/unused/arm', solver_random_seed=value)
                    with self.assertRaises(ValueError):
                        heldout.check_manifest({'solver_random_seed': value})
            with self.assertRaises(KeyError):
                heldout.check_manifest({})
            bind.assert_not_called()
            load.assert_not_called()


class SeedOptionTests(unittest.TestCase):
    def test_default_zero_and_independent_seed_profiles_keep_other_options(self):
        original = copy.deepcopy(options.EXPECTED)
        for role in options.ROLES:
            implicit = options.expected_options(role, 120., start=None)
            explicit = options.expected_options(role, 120., start=None, solver_random_seed=0)
            self.assertEqual(implicit, explicit)
            profiles = [options.expected_options(role, 120., start=None, solver_random_seed=v)
                        for v in (1, 2)]
            for value, profile in zip((1, 2), profiles):
                expected = copy.deepcopy(implicit)
                expected['Int']['random_seed'] = value
                self.assertEqual(profile, expected)
                for kind in original:
                    self.assertIsNot(profile[kind], options.EXPECTED[kind])
                    self.assertIsNot(profiles[0][kind], profiles[1][kind])
            profiles[0]['Int']['threads'] = 99
            self.assertEqual(profiles[1]['Int']['threads'], 2)
        self.assertEqual(options.EXPECTED, original)

    def test_native_commands_differ_only_at_seed_operand(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            start = root/'start.sol'
            start.write_text('mock start')
            for role, initial in ((options.DISCOVERY, None), (options.PROOF_ROLE, start)):
                args = ({'binary': root/'highs'}, root/'model.mps', root/'options', root/'solution', 120.)
                implicit = options.command(*args, start=initial, role=role)
                self.assertEqual(implicit, options.command(*args, start=initial, role=role,
                                                          solver_random_seed=0))
                index = implicit.index('--random_seed') + 1
                for value in (1, 2):
                    expected = list(implicit)
                    expected[index] = str(value)
                    self.assertEqual(options.command(*args, start=initial, role=role,
                                                     solver_random_seed=value), expected)

    def test_invalid_options_rejected_before_native_probe(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'options'
            path.write_text(options.option_text())
            with patch.object(common, 'native_call_guard') as guard, \
                    patch.object(options, '_probe_checked') as checked:
                for value in BAD_SEEDS:
                    with self.subTest(value=value):
                        with self.assertRaises(ValueError):
                            options.expected_options('proof', 120., start=None, solver_random_seed=value)
                        with self.assertRaises(ValueError):
                            options.command({}, 'model', 'options', 'solution', 120., solver_random_seed=value)
                        with self.assertRaises(ValueError):
                            options.probe({}, path, 120., solver_random_seed=value)
                guard.assert_not_called()
                checked.assert_not_called()

    def test_probe_forwards_selected_seed_and_independent_expected_options(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'options'
            path.write_text(options.option_text('discovery'))
            for value in (0, 1, 2):
                with patch.object(common, 'native_call_guard', return_value=nullcontext({})), \
                        patch.object(options, '_probe_checked', return_value={'passed': True}) as checked:
                    self.assertTrue(options.probe({}, path, 120., role='discovery',
                                                  solver_random_seed=value)['passed'])
                arguments = checked.call_args.args
                self.assertEqual(arguments[-1], value)
                self.assertEqual(arguments[-2], options.expected_options('discovery', 120.,
                                 start=None, solver_random_seed=value))
        self.assertEqual(options.EXPECTED['Int']['random_seed'], 0)

    def test_reference_profile_mismatch_fails_before_loading_a_library(self):
        for profile_seed in (True, 0, 2):
            expected = options.expected_options('proof', 120., start=None, solver_random_seed=1)
            expected['Int']['random_seed'] = profile_seed
            with patch.object(options, 'helpers') as helpers:
                with self.assertRaises(ValueError):
                    options._probe_checked({}, '/unused', 120., None, 'proof', expected, 1)
                helpers.assert_not_called()


class FakeHighs:
    """Python-only public API double, including ctypes getter pointer writes."""
    def __init__(self):
        self.options = dict(capi.OPTIONS)
        self.functions = {}
        self.run_seeds = []
        self.runtime = 0.

    def __getattr__(self, name):
        if name not in self.functions:
            self.functions[name] = Mock(name=name, side_effect=lambda *args: self.call(name, *args))
        return self.functions[name]

    def call(self, name, *args):
        if name.startswith('Highs_set') and name.endswith('OptionValue'):
            self.options[args[1].decode()] = args[2].decode() if isinstance(args[2], bytes) else args[2]
        elif name.startswith('Highs_get') and name.endswith('OptionValue'):
            value = self.options[args[1].decode()]
            if name == 'Highs_getStringOptionValue':
                args[2].value = value.encode()
            else:
                args[2]._obj.value = value
        elif name == 'Highs_create':
            return 123
        elif name == 'Highs_getSizeofHighsInt':
            return 4
        elif name == 'Highs_version':
            return b'pure mock'
        elif name == 'Highs_getRunTime':
            return self.runtime
        elif name == 'Highs_getModelStatus':
            return 7
        elif name == 'Highs_run':
            self.run_seeds.append(self.options['random_seed'])
            self.runtime += .25
        return 0


@contextmanager
def mocked_lp(solver_random_seed=0, *, explicit=True):
    """Exercise the real constructor without loading any DSO or setting limits."""
    with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
        root = Path(directory)
        library = root/'libhighs.so'
        fake = FakeHighs()
        hashes = {'libhighs.so': 'library-hash', 'highs_c_api.h': capi.HEADER_SHA,
                  'HighsSolve.cpp': capi.ADVISORY_SOURCE_SHA}
        stack.enter_context(patch.object(capi, 'sha256', side_effect=lambda p: hashes[Path(p).name]))
        stack.enter_context(patch.object(capi, 'runtime_sha', return_value='library-hash'))
        stack.enter_context(patch.object(capi, 'runtime_path', side_effect=lambda p: root/p))
        helper = SimpleNamespace(symbol_provenance=lambda lib, names: {
            name: {'path': str(library), 'sha256': 'library-hash'} for name in names})
        stack.enter_context(patch.object(capi, '_helper', return_value=helper))
        stack.enter_context(patch.object(capi.C, 'CDLL', return_value=fake))
        stack.enter_context(patch.object(capi.time, 'monotonic', return_value=100.))
        lp = capi.PersistentLP(library, root/'native.log', solver_random_seed) if explicit else \
             capi.PersistentLP(library, root/'native.log')
        try:
            yield lp, fake
        finally:
            lp.destroy()


class PersistentLPSeedTests(unittest.TestCase):
    def test_constructor_default_matches_explicit_zero_without_changing_globals(self):
        original = copy.deepcopy(capi.OPTIONS)
        with mocked_lp(explicit=False) as (implicit, _), mocked_lp(0) as (explicit, _):
            self.assertEqual(implicit.options, explicit.options)
            self.assertEqual(implicit.fixed_options, explicit.fixed_options)
            self.assertIsNot(implicit.fixed_options, explicit.fixed_options)
        self.assertEqual(capi.OPTIONS, original)

    def test_selected_seed_precedes_both_runs_and_fixed_profile_is_immutable(self):
        original = copy.deepcopy(capi.OPTIONS)
        for value in (0, 1, 2, 2147483647):
            with self.subTest(seed=value), mocked_lp(value) as (lp, fake):
                expected = dict(original, random_seed=value)
                self.assertEqual(lp.options, expected)
                self.assertEqual(lp.fixed_options, expected)
                self.assertIsInstance(lp.fixed_options, MappingProxyType)
                with self.assertRaises(TypeError):
                    lp.fixed_options['random_seed'] = 9
                self.assertEqual(fake.run_seeds, [])
                lp.expected = {'integrality': np.zeros(1, dtype=np.int32)}
                first = lp.run_with_cumulative_limit(200., native_total_cap=60., reserve_seconds=10.)
                second = lp.run_with_cumulative_limit(200., native_total_cap=60., reserve_seconds=10.)
                self.assertEqual(fake.run_seeds, [value, value])
                self.assertEqual([first['solver_random_seed'], second['solver_random_seed']], [value, value])
                self.assertEqual(second['cumulative_before'], first['cumulative_after'])
                self.assertEqual([r['native_total_cap'] for r in lp.run_records], [60., 60.])
                self.assertEqual([r['declared_final_reserve_seconds'] for r in lp.run_records], [10., 10.])
        self.assertEqual(capi.OPTIONS, original)

    def test_postsolve_seed_mutations_rejected_before_native_setter(self):
        with mocked_lp(1) as (lp, fake):
            lp.expected = {'integrality': np.zeros(1, dtype=np.int32)}
            lp.run_with_cumulative_limit(200.)
            calls = fake.Highs_setIntOptionValue.call_count
            for value in (0, 2, *BAD_SEEDS):
                with self.subTest(value=value), self.assertRaises(ValueError):
                    lp.set_option('random_seed', value)
            self.assertEqual(fake.Highs_setIntOptionValue.call_count, calls)
            lp.set_option('random_seed', 1)
            self.assertEqual(fake.options['random_seed'], 1)

    def test_between_run_drift_blocks_the_second_run(self):
        with mocked_lp(2) as (lp, fake):
            lp.expected = {'integrality': np.zeros(1, dtype=np.int32)}
            lp.run_with_cumulative_limit(200.)
            fake.options['random_seed'] = 1
            with self.assertRaisesRegex(ValueError, 'Frozen option drift'):
                lp.run_with_cumulative_limit(200.)
            self.assertEqual(fake.run_seeds, [2])
            self.assertEqual(len(lp.run_records), 1)

    def test_invalid_constructor_seed_never_loads_library_or_checks_paths(self):
        with patch.object(capi.C, 'CDLL') as load, patch.object(capi, 'sha256') as digest:
            for value in BAD_SEEDS:
                with self.subTest(value=value), self.assertRaises(ValueError):
                    capi.PersistentLP('/unused/libhighs.so', '/unused/native.log', value)
            load.assert_not_called()
            digest.assert_not_called()

    def test_adaptive_constructor_forwards_the_third_argument(self):
        from current_scuc.science import native
        library = Path('/unused/libhighs.so')

        def initialize(instance, library_path, log_path, solver_random_seed=0):
            instance.library_path = Path(library_path)
            instance.lib = FakeHighs()
            instance.I, instance.DP, instance.IP = capi.C.c_int32, capi.C.POINTER(capi.C.c_double), capi.C.POINTER(capi.C.c_int32)
            instance.identity = {'loaded_symbol_provenance': {}}

        helper = SimpleNamespace(symbol_provenance=lambda lib, names: {
            name: {'path': str(library), 'sha256': 'library-hash'} for name in names})
        for value in (0, 1, 2):
            with patch.object(native.core.PersistentLP, '__init__', autospec=True,
                              side_effect=initialize) as constructor, \
                    patch.object(native.core, '_helper', return_value=helper), \
                    patch.object(native, 'runtime_sha', return_value='library-hash'):
                lp = native.PersistentLP(library, '/unused/native.log', value)
                constructor.assert_called_once_with(lp, library, '/unused/native.log', value)


class WorkerSeedTests(unittest.TestCase):
    def run_seed_worker(self, manifest):
        records = {}
        fake_lp = SimpleNamespace(identity={}, options={'random_seed': manifest.get('solver_random_seed')},
            defaults={}, run_records=[], limit_records=[], pass_model=Mock(return_value={}),
            get_runtime=Mock(return_value=0.), diagnostics=Mock(return_value={'fatal': []}), destroy=Mock())
        factory = Mock(name='PersistentLP')
        helpers = SimpleNamespace(output_directory=lambda p: Path(p),
            verify_loaded_runtime=Mock(return_value={}), bundle=Mock(return_value={}),
            sha256=Mock(return_value='hash'),
            write_json=lambda out, name, data, costs: records.update({name: copy.deepcopy(data)}))
        model = SimpleNamespace(model_hashes=Mock(return_value={}))
        prepared = (model, object(), SimpleNamespace(PersistentLP=factory), object(),
                    object(), {}, {}, {}, {})
        with patch.object(seed, 'helpers', return_value=helpers), \
                patch.object(seed, 'storage', return_value=SimpleNamespace(WriteBound=Mock(), NATIVE_FILE_LIMIT=64*1024**2)), \
                patch.object(seed, 'start_output_phase'), patch.object(seed, 'START', 0.), \
                patch.object(seed.time, 'monotonic', return_value=1.), \
                patch.object(seed, 'verify_manifest', return_value=(manifest, {'library': '/unused/lib.so'}, {})), \
                patch.object(seed, 'prepare', return_value=prepared) as prepare, \
                patch.object(seed, 'GuardedLP', return_value=fake_lp) as constructor, \
                patch.object(seed, 'run_seed', side_effect=lambda *a, **k: k['record'].update(passed=True)):
            result = seed.main(['--out', '/unused/seed', '--manifest', '/unused/manifest',
                                '--manifest-sha256', 'hash', '--deadline', '1000'])
        return result, records['result.json'], prepare, constructor, factory

    def test_seed_worker_passes_manifest_seed_to_guarded_native_constructor(self):
        for value in (0, 1, 2):
            with self.subTest(seed=value):
                status, result, prepare, constructor, factory = self.run_seed_worker({'solver_random_seed': value})
                self.assertEqual(status, 0)
                prepare.assert_called_once()
                constructor.assert_called_once_with(factory, '/unused/lib.so', Path('/unused/seed/native.log'), value)
                self.assertEqual(result['solver_random_seed'], value)
                self.assertEqual(result['native_options']['random_seed'], value)

    def test_seed_worker_rejects_missing_or_invalid_seed_before_preparation(self):
        for manifest in ({}, *({'solver_random_seed': value} for value in BAD_SEEDS)):
            with self.subTest(manifest=manifest):
                status, result, prepare, constructor, _ = self.run_seed_worker(manifest)
                self.assertEqual(status, 2)
                self.assertFalse(result['passed'])
                prepare.assert_not_called()
                constructor.assert_not_called()


class PhaseSeedTests(unittest.TestCase):
    def run_phase_to_preparation(self, result, *, selected=1, verified=1):
        """Run the actual phase entry through admission using only mock workers."""
        from current_scuc import heldout, receipts
        records = {}
        helpers = SimpleNamespace(sha256=Mock(return_value='hash'),
            write_json=lambda out, name, data, costs: records.update({name: copy.deepcopy(data)}))
        with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
            root = Path(directory)
            checkpoints = Mock()
            checkpoints.seal.return_value = str(root/'checkpoint.json')
            patches = (
                patch.object(phase, 'helpers', return_value=helpers),
                patch.object(phase, 'START', 0.),
                patch.object(phase.time, 'monotonic', return_value=1.),
                patch.object(phase.fcntl, 'flock'),
                patch.object(common, 'verify_source_freeze'),
                patch.object(binding, 'sha', return_value='hash'),
                patch.object(binding, 'read', return_value={'solver_random_seed': selected}),
                patch.object(binding, 'config', return_value={'numerical_lock': str(root/'lock'), 'python': '/unused/python'}),
                patch.object(binding, 'verify_freeze'),
                patch.object(binding, 'write'),
                patch.object(phase, 'bounded_write'),
                patch.object(heldout, 'config_path', return_value=root/'config'),
                patch.object(receipts, 'validate_source_reference', return_value={'source_manifest_sha256': 'hash'}),
                patch.object(receipts, 'admit_whole', return_value={'block_bytes': 4096}),
                patch.object(receipts, 'Checkpoints', return_value=checkpoints),
                patch.object(receipts, 'failure_metadata', return_value={}),
                patch.object(process_runner, 'apply_limits'),
                patch.object(process_runner, 'require_clean'),
                patch.object(phase, 'storage', return_value=SimpleNamespace(WriteBound=Mock(), NATIVE_FILE_LIMIT=64*1024**2)),
                patch.object(phase, 'start_output_phase'),
                patch.object(phase, 'verify_manifest', return_value=({'solver_random_seed': verified}, {}, {})),
                patch.object(phase, 'read_complete', return_value=result),
                patch.object(phase, 'seed_eligible'),
                patch.object(phase, 'terminal_gate', return_value=False),
                patch.dict(os.environ),
            )
            for item in patches:
                stack.enter_context(item)
            process = stack.enter_context(patch.object(process_runner, 'run', return_value={'process_wall_seconds': 1.}))
            prepare = stack.enter_context(patch.object(phase, 'prepare', side_effect=RuntimeError('stop after seed provenance')))
            status = phase.main(['--out', str(root/'candidate'), '--source-manifest', str(root/'source'),
                '--source-manifest-sha256', 'hash', '--source-reference', str(root/'reference'),
                '--arm-manifest', str(root/'arm'), '--arm-manifest-sha256', 'hash'])
        self.assertEqual(status, 2)
        return records['result.json'], prepare, process

    def test_matching_worker_seed_is_admitted_to_parent_preparation(self):
        for value in (0, 1, 2):
            result = {'verified_manifest_sha256': 'hash', 'solver_random_seed': value,
                      'native_options': {'random_seed': value}}
            with self.subTest(seed=value):
                state, prepare, process = self.run_phase_to_preparation(result, selected=value, verified=value)
                prepare.assert_called_once()
                process.assert_called_once()
                self.assertEqual(state['solver_random_seed'], value)
                self.assertEqual(state['seed'], result)
                self.assertIn('stop after seed provenance', state['error'])

    def test_seed_worker_missing_mismatched_or_mistyped_provenance_fails_closed(self):
        good = {'verified_manifest_sha256': 'hash', 'solver_random_seed': 1,
                'native_options': {'random_seed': 1}}
        cases = []
        for path in (('solver_random_seed',), ('native_options', 'random_seed')):
            for value in (None, 0, 2, True, 1.0, math.nan):
                result = copy.deepcopy(good)
                target = result
                for key in path[:-1]:
                    target = target[key]
                if value is None:
                    del target[path[-1]]
                else:
                    target[path[-1]] = value
                cases.append(result)
        result = copy.deepcopy(good)
        del result['native_options']
        cases.append(result)
        for result in cases:
            with self.subTest(result=result):
                state, prepare, process = self.run_phase_to_preparation(result)
                prepare.assert_not_called()
                process.assert_called_once()
                self.assertFalse(state['passed'])
                self.assertNotIn('seed', state)

    def test_changed_arm_seed_blocks_even_the_mock_worker_launch(self):
        state, prepare, process = self.run_phase_to_preparation({}, selected=1, verified=2)
        prepare.assert_not_called()
        process.assert_not_called()
        self.assertIn('Arm solver seed changed', state['error'])


def carry_state(value):
    rows = []
    for call in (1, 2, 3):
        command = ['/unused/highs', '/unused/model.mps', '--random_seed', str(value)]
        rows.append({'call': call, 'solver_random_seed': value, 'command': command,
                     'native_limit_request': {'argv': list(command)}})
    return {'solver_random_seed': value,
            'seed': {'solver_random_seed': value, 'native_options': {'random_seed': value}},
            'trace': rows}


class CarrySeedTests(unittest.TestCase):
    def test_all_recorded_calls_and_optional_arm_bind_without_mutation(self):
        for value in (0, 1, 2, 2147483647):
            state = carry_state(value)
            original = copy.deepcopy(state)
            self.assertEqual(carry.checked_solver_random_seed(state), value)
            self.assertEqual(carry.checked_solver_random_seed(state, {'solver_random_seed': value}), value)
            self.assertEqual(state, original)

    def test_missing_typed_provenance_never_falls_back_to_zero(self):
        for path in (('solver_random_seed',), ('seed',), ('seed', 'solver_random_seed'),
                     ('seed', 'native_options'), ('seed', 'native_options', 'random_seed'),
                     ('trace',), ('trace', 0, 'solver_random_seed'), ('trace', 1, 'solver_random_seed'),
                     ('trace', 2, 'solver_random_seed'), ('trace', 0, 'command'),
                     ('trace', 0, 'native_limit_request', 'argv')):
            state = carry_state(0)
            target = state
            for key in path[:-1]:
                target = target[key]
            del target[path[-1]]
            with self.subTest(path=path), self.assertRaises((KeyError, ValueError)):
                carry.checked_solver_random_seed(state)
        with self.assertRaises((KeyError, ValueError)):
            carry.checked_solver_random_seed(carry_state(0), {})

    def test_mismatched_and_mistyped_seed_at_each_provenance_boundary(self):
        for path in (('solver_random_seed',), ('seed', 'solver_random_seed'),
                     ('seed', 'native_options', 'random_seed'),
                     ('trace', 0, 'solver_random_seed'), ('trace', 1, 'solver_random_seed'),
                     ('trace', 2, 'solver_random_seed')):
            for value in (0, 2, *BAD_SEEDS):
                state = carry_state(1)
                target = state
                for key in path[:-1]:
                    target = target[key]
                target[path[-1]] = value
                with self.subTest(path=path, value=value), self.assertRaises(ValueError):
                    carry.checked_solver_random_seed(state)
        for value in (0, 2, *BAD_SEEDS):
            with self.subTest(arm=value), self.assertRaises(ValueError):
                carry.checked_solver_random_seed(carry_state(1), {'solver_random_seed': value})

    def test_each_native_command_and_wrapped_request_must_match(self):
        for index in range(3):
            for command in (['/unused/highs'], ['/unused/highs', '--random_seed', '2'],
                            ['/unused/highs', '--random_seed', '01'],
                            ['/unused/highs', '--random_seed', '1', '--random_seed', '1']):
                state = carry_state(1)
                state['trace'][index]['command'] = command
                state['trace'][index]['native_limit_request']['argv'] = list(command)
                with self.subTest(call=index, command=command), self.assertRaises(ValueError):
                    carry.checked_solver_random_seed(state)
            state = carry_state(1)
            state['trace'][index]['native_limit_request']['argv'][-1] = '2'
            with self.subTest(request=index), self.assertRaises(ValueError):
                carry.checked_solver_random_seed(state)

    def test_proof_probe_rejects_bool_and_float_that_compare_equal_to_seed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            start = root/'point.sol'
            start.write_text('mock start')
            opt = root/'solver.options'
            opt.write_text(options.option_text('proof'))
            readback = root/'options-readback.json'
            profile = options.expected_options('proof', 120., start=start, solver_random_seed=1)
            probe = dict(passed=True, role='proof', solver_random_seed=1,
                         options={k: v for values in profile.values() for k, v in values.items()},
                         options_sha256=carry.g.sha(opt))
            readback.write_text(json.dumps(probe))
            state = carry_state(1)
            state['carry_preparations'] = [{'preparation': {
                'passed': True, 'solver_random_seed': 1, 'start': {'path': str(start)}}}]
            record = {'evidence': {'source_master_identity': {}}}
            identity = {'model_path': str(root/'master.mps')}
            with patch.object(carry, 'validate_transition', return_value=record), \
                    patch.object(carry, 'same_transition_master'):
                self.assertIs(carry.verify_transition_proof(state, identity, probe, start), record)
                for path in (('solver_random_seed',), ('options', 'random_seed')):
                    for value in (True, 1.0):
                        bad = copy.deepcopy(probe)
                        target = bad
                        for key in path[:-1]:
                            target = target[key]
                        target[path[-1]] = value
                        readback.write_text(json.dumps(bad))
                        with self.subTest(path=path, value=value), self.assertRaisesRegex(ValueError, 'solver_random_seed'):
                            carry.verify_transition_proof(state, identity, bad, start)

    def test_discovery_probe_rejects_equal_but_mistyped_seed_before_receipt(self):
        from current_scuc.diagnostics import interval
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rd = root/'mip-01'
            rd.mkdir()
            state = carry_state(1)
            state.update(run_directory=str(root), quality_failed=False, mechanism_failed=False,
                         integer_target_identity_sha256='target')
            state['trace'] = state['trace'][:1]
            row = state['trace'][0]
            identity = dict(integer_target_identity_sha256='target', network_oracle_identity_sha256='scope',
                            hard_zero_subset={'identity_sha256': 'subset'})
            for key, name in (('model', 'master.mps'), ('expected', 'expected.json'),
                              ('api_report', 'report.json'), ('row_sidecar', 'rows.json')):
                path = rd/name
                path.write_text('{}')
                identity[key+'_path'] = str(path)
                identity[key+'_sha256'] = carry.g.sha(path)
            row.update(role='discovery', incumbent_input=None, no_basis_or_search_state_input=True,
                process={}, native_limit_seconds=120., allocation_seconds=180.,
                report=dict(role='discovery', status='Solution limit reached', discovery_stop_activated=True,
                    model_definition_diagnostics=[], clean_return=True, loaded_library_identity_valid=True,
                    identities_valid=True, parent_report_identity_valid=True, bound_status_valid=False,
                    certificate_bound_eligible=False, global_lower=None),
                master_quality={'passed': True, 'point_rounded': False},
                selected_endpoint_interval=interval(0., 10.), selected_endpoint_call=1,
                continuation_support=dict(passed=False, materially_violated_rows=0, threshold_MW=1e-5,
                                          maximum_positive_residual_MW=0.),
                master_identity=identity,
                evaluation=dict(provisional_upper=10., full_scope_identity_sha256='scope',
                                target_subset_quality={'subset_identity_sha256': 'subset'}))
            opt = rd/'solver.options'
            opt.write_text(options.option_text('discovery'))
            readback = rd/'options-readback.json'
            (rd/'native-exec.json').write_text('{}')
            profile = options.expected_options('discovery', 120., start=None, solver_random_seed=1)
            probe = dict(passed=True, role='discovery', solver_random_seed=1,
                         options={k: v for values in profile.values() for k, v in values.items()},
                         options_sha256=carry.g.sha(opt))

            def save(value):
                readback.write_text(json.dumps(value))
                row['options_artifacts'] = dict(options_path=str(opt), options_sha256=carry.g.sha(opt),
                    readback_path=str(readback), readback_sha256=carry.g.sha(readback))

            with patch.object(carry, 'module'), patch.object(carry, 'select_point'), \
                    patch.object(process_runner, 'require_clean'), \
                    patch.object(carry, 'native_limits', side_effect=RuntimeError('past probe validation')) as receipt:
                save(probe)
                with self.assertRaisesRegex(RuntimeError, 'past probe validation'):
                    carry.transition_evidence(state)
                receipt.reset_mock()
                for path in (('solver_random_seed',), ('options', 'random_seed')):
                    for value in (True, 1.0):
                        bad = copy.deepcopy(probe)
                        target = bad
                        for key in path[:-1]:
                            target = target[key]
                        target[path[-1]] = value
                        save(bad)
                        with self.subTest(path=path, value=value), self.assertRaisesRegex(ValueError, 'solver_random_seed'):
                            carry.transition_evidence(state)
                receipt.assert_not_called()


if __name__ == '__main__':
    unittest.main()
