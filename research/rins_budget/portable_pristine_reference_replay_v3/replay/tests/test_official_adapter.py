"""Pure adapter tests: no solver, scientific import, or native-library load."""
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

PACKAGE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('official_prepare', PACKAGE/'prepare_replay.py')
prepare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)
import cold_screen_pair
import trial_policy

STANDARD_MIP = '''threads = 2
parallel = off
presolve = on
write_solution_to_file = true
write_solution_style = 0
log_dev_level = 1
highs_analysis_level = 128
mip_rel_gap = 0.01
mip_improving_solution_save = false
mip_lp_solver = choose
mip_ipm_solver = choose
'''

class Tests(unittest.TestCase):
    def test_exact_standard_options_and_discovery_only_delta(self):
        self.assertEqual(cold_screen_pair.options_text('mip', False), STANDARD_MIP)
        self.assertEqual(trial_policy.options_text(trial_policy.PROOF), STANDARD_MIP)
        self.assertEqual(trial_policy.options_text(trial_policy.DISCOVERY),
                         STANDARD_MIP+'mip_max_improving_sols = 1\n')
        with self.assertRaises(cold_screen_pair.ContractError):
            cold_screen_pair.options_text('mip', True)
        for role in (trial_policy.PROOF, trial_policy.DISCOVERY):
            with self.assertRaises(cold_screen_pair.ContractError):
                trial_policy.validate_options(role, trial_policy.options_text(role)+'unknown_option = false\n')

    def test_package_is_closed_and_old_core_bytes_are_preserved(self):
        manifest = prepare.release(PACKAGE)
        self.assertEqual(manifest['source_commit'], 'd547a3ad8af5399651187fb0e133cf0e42615b82')
        old = PACKAGE.parent/'pg89-corrected-package-v1'
        names = [n for n in manifest['files'] if n.startswith('payload/')]
        changed = ['payload/combined_screening_driver/cold_screen_pair.py']
        self.assertEqual([n for n in names if prepare.sha(PACKAGE/n) != prepare.sha(old/n)], changed)
        self.assertFalse(any(n.startswith('patches/') for n in manifest['files']))

    def test_complete_official_source_inventory_and_stale_source_rejection(self):
        source = PACKAGE.parent/'official-reference-v3/source'
        record = prepare.source_inventory(source)
        self.assertEqual(record['source_files'], 1006)
        self.assertEqual(record['base_commit'], 'd547a3ad8af5399651187fb0e133cf0e42615b82')
        self.assertTrue(record['exact_tree_verified'])
        with self.assertRaises(prepare.BindingError):
            prepare.source_inventory(PACKAGE.parent/'correctness-reference-v2/source')

    def test_main_and_extras_are_bound_to_same_build_without_loading(self):
        with tempfile.TemporaryDirectory(prefix='official_binding_') as directory:
            root = Path(directory)
            source = root/'source'; source.mkdir()
            build = root/'build'; (build/'bin').mkdir(parents=True); (build/'lib').mkdir()
            metadata = build/'CMakeFiles/mock'; metadata.mkdir(parents=True)
            (metadata/'CMakeCCompiler.cmake').write_text('# pure metadata fixture\n')
            fields = {'CMAKE_BUILD_TYPE':'Release', 'FAST_BUILD':'ON', 'BUILD_SHARED_LIBS':'ON',
                'BUILD_SHARED_EXTRAS_LIB':'ON', 'HIPO':'OFF', 'HIGHSINT64':'OFF',
                'BUILD_TESTING':'ON', 'ALL_TESTS':'ON', 'CMAKE_C_FLAGS':'', 'CMAKE_CXX_FLAGS':'',
                'CMAKE_C_FLAGS_RELEASE':'-O3 -DNDEBUG', 'CMAKE_CXX_FLAGS_RELEASE':'-O3 -DNDEBUG',
                'CMAKE_EXE_LINKER_FLAGS':'-flto=2', 'CMAKE_SHARED_LINKER_FLAGS':'-flto=2',
                'CMAKE_HOME_DIRECTORY':str(source)}
            (build/'CMakeCache.txt').write_text(''.join(k+':STRING='+v+'\n' for k,v in fields.items()))
            (build/'HConfig.h').write_text('#define FAST_BUILD\n#define CMAKE_BUILD_TYPE "Release"\n')
            (build/'bin/highs').write_text('not executable; never launched\n')
            for name in ('libhighs.so', 'libhighs_extras.so'):
                (build/'lib'/(name+'.1.99.0')).write_text('fake bytes '+name)
                (build/'lib'/name).symlink_to(name+'.1.99.0')
                (build/'lib'/(name+'.1')).symlink_to(name+'.1.99.0')
            record = prepare.build_identity(source, build)
            self.assertEqual(Path(record['library']).name, 'libhighs.so.1.99.0')
            self.assertEqual(Path(record['extras']).name, 'libhighs_extras.so.1.99.0')
            self.assertEqual(len(record['aliases']), 6)
            self.assertEqual(record['flags']['BUILD_SHARED_EXTRAS_LIB'], 'ON')
            for key in ('CMAKE_EXE_LINKER_FLAGS','CMAKE_SHARED_LINKER_FLAGS','CMAKE_MODULE_LINKER_FLAGS'):
                bad = dict(fields, **{key:'-flto=8'})
                with patch.object(prepare, 'cmake_cache', return_value=bad), self.assertRaises(prepare.BindingError):
                    prepare.build_identity(source, build)
            bad = dict(fields, BUILD_SHARED_EXTRAS_LIB='OFF')
            with patch.object(prepare, 'cmake_cache', return_value=bad), self.assertRaises(prepare.BindingError):
                prepare.build_identity(source, build)

    def test_pure_test_process_did_not_import_scientific_packages(self):
        self.assertFalse({'numpy','scipy','highspy'} & set(sys.modules))

if __name__ == '__main__':
    unittest.main()
