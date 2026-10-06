"""Pure fixed-fixture checks; no model generation, native loads, or solve."""
import copy
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from current_scuc import case_binding
from tests.fixed_triangle import fixture, family_fixture, require_expected_quality


class FixedTriangleTest(unittest.TestCase):
    def test_only_declared_existing_startup_delta(self):
        original, pairs = fixture()
        expected = copy.deepcopy(original)
        for unit in expected['Generators'].values():
            unit['Startup costs ($)'] = [1.]
        family, family_pairs = family_fixture()
        self.assertEqual(family, expected)
        self.assertEqual(pairs, family_pairs)
        self.assertEqual(pairs, ((0, 1), (1, 2)))
        self.assertEqual(len(family['Buses']), 3)
        self.assertEqual(family['Parameters']['Time horizon (h)'], 2)

    def test_production_horizon_rejects_fixed_tiny(self):
        data, _ = family_fixture()
        with patch.object(case_binding, 'source_helpers', return_value=SimpleNamespace()):
            with self.assertRaisesRegex(ValueError, 'Source horizon'):
                case_binding.source_contract(data)

    def test_known_quality_is_nonpass_and_never_relaxed(self):
        quality = dict(passed=False, tolerance_MWh=1e-5,
                       positive_slack_totals_MWh=dict(load_shedding=0., reserve_shortfall=0., shared_overflow=2.25))
        self.assertTrue(require_expected_quality(quality))
        for changed in ({**quality, 'passed': True}, {**quality, 'tolerance_MWh': 1.},
                        {**quality, 'positive_slack_totals_MWh': dict(load_shedding=0., reserve_shortfall=0., shared_overflow=0.)}):
            with self.assertRaises(ValueError):
                require_expected_quality(changed)


if __name__ == '__main__':
    unittest.main()
