"""ABI/provider validation with synthetic records; no DSO load or C API calls."""
import copy
from pathlib import Path
import site
import sys
import unittest
from unittest.mock import patch

from portable_runtime import BindingError
import runtime_inspect as inspect_runtime
from test_portable_runtime import TemporaryTests


class AbiProviderTests(unittest.TestCase):
    def setUp(self):
        self.library = Path('/mock/build/libhighs.so').resolve()
        self.digest = 'a' * 64
        self.providers = {
            name: {'path': str(self.library), 'sha256': self.digest}
            for name in inspect_runtime.C_SYMBOLS
        }

    def validate(self, size=4, providers=None):
        # Guard against accidentally extending this pure gate into an API call.
        with patch.object(inspect_runtime.C, 'CDLL', side_effect=AssertionError('No actual DSO loading allowed')):
            inspect_runtime.validate_abi_providers(size, self.providers if providers is None else providers,
                                                  self.library, self.digest)

    def test_exact_32bit_abi_and_all_providers_accepted(self):
        self.validate()

    def test_non_32bit_or_missing_abi_rejected(self):
        for size in (None, 0, 1, 2, 8, 16, '4', True, False):
            with self.subTest(size=size), self.assertRaises(BindingError):
                self.validate(size)

    def test_every_required_symbol_must_be_present(self):
        for name in self.providers:
            providers = copy.deepcopy(self.providers); del providers[name]
            with self.subTest(name=name), self.assertRaises(BindingError):
                self.validate(providers=providers)

    def test_each_provider_path_and_digest_must_match_selected_dso(self):
        for name in self.providers:
            for key, wrong in (('path', '/mock/foreign/libhighs.so'), ('sha256', 'b' * 64)):
                providers = copy.deepcopy(self.providers); providers[name][key] = wrong
                with self.subTest(name=name, key=key), self.assertRaises(BindingError):
                    self.validate(providers=providers)

    def test_extra_symbol_or_incomplete_provider_rejected(self):
        providers = copy.deepcopy(self.providers)
        providers['Highs_unrequested'] = {'path': str(self.library), 'sha256': self.digest}
        with self.assertRaises(BindingError): self.validate(providers=providers)
        for entry in ({}, {'path': str(self.library)}, {'sha256': self.digest},
                      {'path': str(self.library), 'sha256': self.digest, 'untrusted': True}):
            providers = copy.deepcopy(self.providers)
            providers[inspect_runtime.C_SYMBOLS[0]] = entry
            with self.subTest(entry=entry), self.assertRaises(BindingError):
                self.validate(providers=providers)


class StartupInspectionTests(TemporaryTests):
    def test_debian_extra_site_hook_rejected_without_scientific_import(self):
        ordinary = self.root / 'ordinary-site'; ordinary.mkdir()
        debian = self.root / 'debian-dist-packages'; debian.mkdir()
        (debian / 'unexpected.pth').write_text('raise AssertionError("must never execute")')
        with patch.object(inspect_runtime.sys, 'executable', str(self.root / 'bin/python')), \
             patch.object(inspect_runtime.sys, 'path', [str(self.root)]), \
             patch.object(inspect_runtime.sysconfig, 'get_path', return_value=str(ordinary)), \
             patch.object(site, 'getsitepackages', return_value=[str(debian)]) as sites, \
             patch.object(inspect_runtime.platform, 'libc_ver', return_value=('glibc', 'mock')):
            with self.assertRaisesRegex(BindingError, 'startup hooks'):
                inspect_runtime.startup()
        sites.assert_called_once()
        self.assertNotIn('numpy', sys.modules)
        self.assertNotIn('scipy', sys.modules)


if __name__ == '__main__':
    unittest.main(verbosity=2)
