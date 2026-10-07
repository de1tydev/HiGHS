"""Small exhaustive feasible witnesses and contract/boundary regressions."""

import itertools
import unittest
from fractions import Fraction as F

from capacity_abstention import SUPPORTED_SCOPE, UnitBounds, assess_adequacy


def unit(name="g", cap=2, upper=1, hint=None):
    return UnitBounds(name, [cap], [upper], [hint])


def assess(units=None, load=(1,), reserve=(0,), **overrides):
    kwargs = dict(horizon=len(load), units=[unit()] if units is None else units,
                  load=load, hard_reserve=reserve, scope=SUPPORTED_SCOPE,
                  complete_scope=True, hard_zero_load_shedding=True,
                  hard_zero_reserve_shortfall=True)
    kwargs.update(overrides)
    return assess_adequacy(**kwargs)


class CapacityTests(unittest.TestCase):
    def test_enumerated_feasible_dispatch_and_two_reserve_products(self):
        # Build independent feasible witnesses BEFORE invoking the screen.
        # Each tuple is (commitment, dispatch, reserve1, reserve2).
        states = [s for s in itertools.product(range(2), range(3), range(3), range(3))
                  if sum(s[1:]) <= 2 * s[0]]
        checked = 0
        for a, b in itertools.product(states, repeat=2):
            for hints in itertools.product((None, a[0]), (None, b[0])):
                for uppers in itertools.product((a[0], 1), (b[0], 1)):
                    result = assess([unit("a", 2, uppers[0], hints[0]),
                                     unit("b", 2, uppers[1], hints[1])],
                                    load=[a[1] + b[1]],
                                    reserve=[sum(a[2:]) + sum(b[2:])])
                    self.assertEqual(result.status, "retain_unknown", (a, b, hints, uppers))
                    self.assertEqual(result.network_feasibility, "unknown")
                    checked += 1
        self.assertEqual(checked, 1936)

    def test_hint_release_and_current_capacity_are_monotone(self):
        fixed = assess([unit("a", 2, 1, 0), unit("b", 1)], load=[2])
        released = assess([unit("a", 2, 1, None), unit("b", 1)], load=[2])
        larger = assess([unit("a", 3, 1, None), unit("b", 1)], load=[2])
        self.assertEqual(fixed.status, "abstain")
        self.assertEqual(released.status, "retain_unknown")
        self.assertEqual(larger.status, "retain_unknown")
        self.assertEqual([r.hours[0].possible_capacity for r in (fixed, released, larger)],
                         [1, 3, 4])
        # A released unit formerly fixed off gets its CURRENT upper, not zero
        # or its unconstrained nameplate value.
        derated = assess([unit(cap=4, upper="1/2")], load=[3])
        self.assertEqual(derated.hours[0].possible_capacity, 2)
        self.assertEqual(derated.status, "abstain")
        self.assertEqual(assess([unit(cap=4, upper=1)], load=[3]).status, "retain_unknown")

    def test_all_hours_and_current_load_plus_hard_reserve(self):
        result = assess([UnitBounds("g", [4, 5, 6], [1, 1, 1], [None, 0, 1])],
                        load=[3, 1, 5], reserve=[1, 0, 2])
        self.assertEqual(result.status, "abstain")
        self.assertEqual(result.violating_hours, (1, 2))
        self.assertEqual([h.deficit for h in result.hours], [0, 1, 1])
        self.assertEqual(result.network_feasibility, "unknown")

    def test_exact_boundary_and_float_vs_decimal_semantics(self):
        decimal = assess([unit(cap="0.3")], load=["0.1"], reserve=["0.2"])
        self.assertEqual(decimal.status, "retain_unknown")
        self.assertEqual(decimal.hours[0].deficit, 0)
        binary = assess([unit(cap=0.3)], load=[0.1], reserve=[0.2])
        self.assertEqual(binary.status, "abstain")
        delta = F(0.1) + F(0.2) - F(0.3)
        self.assertEqual(binary.hours[0].deficit, delta)
        self.assertGreater(delta, 0)
        self.assertEqual(assess([unit(cap=0.3)], load=[0.1], reserve=[0.2],
                               feasibility_allowance=[delta]).status, "retain_unknown")
        self.assertEqual(assess([unit(cap=0.3)], load=[0.1], reserve=[0.2],
                               feasibility_allowance=[delta / 2]).status, "abstain")

    def test_aggregate_allowance_protects_toleranced_witness(self):
        # Two capacity rows each permit 1/10 MW excess, balance underserves
        # by 1/10 and reserve underserves by 1/10. Total allowance is 4/10,
        # not the single-row tolerance 1/10.
        units = [unit("a", 1), unit("b", 1)]
        dispatch, reserves = [F(11, 10), 0], [0, F(11, 10)]
        load, reserve = sum(dispatch) + F(1, 10), sum(reserves) + F(1, 10)
        self.assertEqual(assess(units, [load], [reserve]).status, "abstain")
        allowed = assess(units, [load], [reserve], feasibility_allowance=["0.4"])
        self.assertEqual(allowed.status, "retain_unknown")
        self.assertEqual(allowed.hours[0].deficit, F(2, 5))
        self.assertEqual(assess(units, [load], [reserve],
                               feasibility_allowance=["0.1"]).status, "abstain")

    def test_allowances_apply_per_hour(self):
        result = assess([UnitBounds("g", [1, 1], [1, 1], [None, None])],
                        load=["1.1", "1.1"], reserve=[0, 0],
                        feasibility_allowance=["0.1", 0])
        self.assertEqual(result.violating_hours, (1,))

    def test_empty_complete_supply(self):
        self.assertEqual(assess([], load=[0]).status, "retain_unknown")
        self.assertEqual(assess([], load=[1]).status, "abstain")

    def test_soft_slack_and_unverified_scope_are_unsupported(self):
        for overrides in ({"scope": "regional"}, {"scope": None},
                          {"complete_scope": False}, {"complete_scope": 1},
                          {"hard_zero_load_shedding": False},
                          {"hard_zero_reserve_shortfall": False},
                          {"hard_zero_reserve_shortfall": "true"}):
            with self.subTest(overrides=overrides):
                result = assess(load=[999], **overrides)
                self.assertEqual(result.status, "unsupported")
                self.assertEqual(result.hours, ())

    def test_malformed_nonfinite_negative_and_shapes_are_unsupported(self):
        cases = [{"load": [x]} for x in (True, -1, "-0.1", "NaN", "inf", "1/0",
                                         float("nan"), float("inf"), object())]
        cases += [{"horizon": x} for x in (0, -1, True, 1.0)]
        cases += [{"units": [unit(cap=x)]} for x in (-1, "NaN")]
        cases += [{"units": [unit(upper=x)]} for x in (-1, 2, "inf")]
        cases += [{"units": [unit(hint=x)]} for x in (-1, 2, True, 1.0, "1")]
        cases += [{"units": [unit(upper=0, hint=1)]},
                  {"units": [unit(), unit()]}, {"units": [unit(name="")]},
                  {"units": None}, {"units": [None]},
                  {"units": [UnitBounds("g", [], [1], [None])]},
                  {"units": [UnitBounds("g", [1], [1], [])]},
                  {"hard_reserve": [-1]}, {"hard_reserve": []},
                  {"load": "1"}, {"load": None},
                  {"feasibility_allowance": [-1]},
                  {"feasibility_allowance": [float("inf")]},
                  {"feasibility_allowance": []}]
        for changes in cases:
            kwargs = dict(horizon=1, units=[unit()], load=[1], hard_reserve=[0],
                          scope=SUPPORTED_SCOPE, complete_scope=True,
                          hard_zero_load_shedding=True, hard_zero_reserve_shortfall=True)
            kwargs.update(changes)
            with self.subTest(changes=changes):
                result = assess_adequacy(**kwargs)
                self.assertEqual(result.status, "unsupported")
                self.assertEqual(result.hours, ())

    def test_validate_later_hours_before_mathematical_rejection(self):
        result = assess([UnitBounds("g", [0, "NaN"], [1, 1], [None, None])],
                        load=[5, 5], reserve=[0, 0])
        self.assertEqual(result.status, "unsupported")
        self.assertEqual(result.violating_hours, ())


if __name__ == "__main__":
    unittest.main()
