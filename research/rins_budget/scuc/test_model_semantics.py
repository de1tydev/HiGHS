#!/usr/bin/env python3
"""Portable, solver-free regression tests for the custom SCUC generator.

Place this file beside generate.py and run:
    python -m unittest -v test_model_semantics

All fixtures are tiny synthetic instances. Tests inspect the actual generated
rows and bounds; they do not solve models, read benchmark data, or write files.
The exhaustive test checks integer schedules, not LP-relaxation strength or
equivalence with every formulation available in UnitCommitment.jl.
"""

import itertools
import unittest

import generate


def instance(hours=7, uptime=1, downtime=1, initial=-6):
    """One zero-load bus; zero dispatch is feasible for either commitment."""
    return {
        "Parameters": {"Version": "0.3", "Time horizon (h)": hours},
        "Buses": {"b": {"Load (MW)": [0.0] * hours}},
        "Generators": {
            "g": {
                "Bus": "b",
                "Production cost curve (MW)": [0.0, 10.0],
                "Production cost curve ($)": [0.0, 10.0],
                "Startup delays (h)": [downtime, downtime + 2, downtime + 4],
                "Startup costs ($)": [10.0, 20.0, 30.0],
                "Minimum uptime (h)": uptime,
                "Minimum downtime (h)": downtime,
                "Initial status (h)": initial,
                "Initial power (MW)": 0.0,
            }
        },
        "Transmission lines": {},
        "Contingencies": {},
        "Reserves": {},
    }


def duration_semantics(schedule, initial, uptime, downtime, delays, costs):
    """Independent chronological oracle, without rolling-window equations."""
    previous = int(initial > 0)
    duration = abs(initial)
    feasible = True
    startup_costs = []
    for current in schedule:
        cost = 0.0
        if current != previous:
            minimum = uptime if previous else downtime
            feasible = feasible and duration >= minimum
            if current:
                applicable = [c for delay, c in zip(delays, costs)
                              if duration >= delay]
                # No category is applicable to an invalid, too-early startup.
                cost = max(applicable, default=0.0)
            duration = 0
        startup_costs.append(cost)
        duration += 1
        previous = current
    return feasible, startup_costs


def unpack_rows(model):
    rows = [[] for _ in model.rhs]
    for row, column, coefficient in zip(model.ri, model.ci, model.val):
        rows[row].append((column, coefficient))
    return [(sense, rhs, terms)
            for sense, rhs, terms in zip(model.sense, model.rhs, rows)]


def satisfies(row, values):
    sense, rhs, terms = row
    lhs = sum(coefficient * values[column] for column, coefficient in terms)
    if sense == "E":
        return abs(lhs - rhs) <= 1e-10
    if sense == "L":
        return lhs <= rhs + 1e-10
    if sense == "G":
        return lhs >= rhs - 1e-10
    raise AssertionError("Unknown row sense: " + sense)


class CommitmentSemanticsTests(unittest.TestCase):
    def test_exhaustive_minimum_times_and_startup_epigraph(self):
        hours = 7
        schedules = list(itertools.product((0, 1), repeat=hours))
        initial_states = list(range(-6, 0)) + list(range(1, 7))
        checked = 0
        for uptime, downtime, initial in itertools.product(
                range(1, 5), range(1, 5), initial_states):
            data = instance(hours, uptime, downtime, initial)
            unit = data["Generators"]["g"]
            model, _ = generate.build(data, hours, "uc")
            columns = {name: index for index, name in enumerate(model.names)}
            rows = unpack_rows(model)
            binary_columns = [j for j, binary in enumerate(model.binary)
                              if binary]
            commitment_rows = [row for row in rows
                               if all(model.binary[j] for j, _ in row[2])]
            startup_rows = []
            for t in range(hours):
                column = columns[f"sc_g_{t}"]
                selected = [row for row in rows
                            if any(j == column for j, _ in row[2])]
                self.assertEqual(len(selected), 3)
                self.assertEqual(model.obj[column], 1.0)
                for sense, _, terms in selected:
                    self.assertEqual(sense, "G")
                    self.assertEqual(dict(terms)[column], 1.0)
                startup_rows.append((column, selected))

            for schedule in schedules:
                expected_feasible, expected_costs = duration_semantics(
                    schedule, initial, uptime, downtime,
                    unit["Startup delays (h)"], unit["Startup costs ($)"],
                )
                values = [0.0] * len(model.names)
                previous = int(initial > 0)
                for t, current in enumerate(schedule):
                    values[columns[f"u_g_{t}"]] = current
                    values[columns[f"y_g_{t}"]] = int(current > previous)
                    values[columns[f"z_g_{t}"]] = int(current < previous)
                    previous = current
                actual_feasible = (
                    all(model.lb[j] <= values[j] <= model.ub[j]
                        for j in binary_columns)
                    and all(satisfies(row, values) for row in commitment_rows)
                )
                context = (uptime, downtime, initial, schedule)
                self.assertEqual(actual_feasible, expected_feasible, context)
                if expected_feasible:
                    for t, (column, selected) in enumerate(startup_rows):
                        lower_bounds = [model.lb[column]]
                        for _, rhs, terms in selected:
                            lower_bounds.append(rhs - sum(
                                coefficient * values[j]
                                for j, coefficient in terms if j != column
                            ))
                        self.assertEqual(max(lower_bounds), expected_costs[t],
                                         (context, t))
                checked += 1
        self.assertEqual(checked, 24576)

    def test_residual_initial_time_fixings(self):
        for initial, uptime, downtime, expected in (
            (1, 3, 1, [1.0, 1.0, None]),
            (-1, 1, 3, [0.0, 0.0, None]),
            (3, 3, 1, [None, None, None]),
            (-3, 1, 3, [None, None, None]),
        ):
            with self.subTest(initial=initial):
                model, _ = generate.build(
                    instance(3, uptime, downtime, initial), 3, "uc")
                for t, fixed in enumerate(expected):
                    j = model.names.index(f"u_g_{t}")
                    bounds = (model.lb[j], model.ub[j])
                    self.assertEqual(bounds, (0.0, 1.0) if fixed is None
                                     else (fixed, fixed))

    def test_must_run_cannot_override_initial_downtime(self):
        data = instance(3, downtime=3, initial=-1)
        data["Generators"]["g"]["Must run?"] = [True, False, False]
        with self.assertRaisesRegex(AssertionError, "initial downtime"):
            generate.build(data, 3, "uc")

    def test_must_run_is_allowed_after_residual_downtime(self):
        data = instance(3, downtime=3, initial=-1)
        data["Generators"]["g"]["Must run?"] = [False, False, True]
        model, _ = generate.build(data, 3, "uc")
        j = model.names.index("u_g_2")
        self.assertEqual((model.lb[j], model.ub[j]), (1.0, 1.0))


class SupportedSchemaTests(unittest.TestCase):
    def test_synthetic_supported_input(self):
        generate.check_schema(instance(), 7)

    def test_rejects_unit_contingency_spellings(self):
        for key in ("Affected units", "Affected generators"):
            with self.subTest(key=key):
                data = instance()
                data["Contingencies"] = {
                    "c": {"Affected lines": ["line"], key: ["g"]}
                }
                with self.assertRaises(AssertionError):
                    generate.check_schema(data, 7)

    def test_rejects_unsupported_schema_features(self):
        mutations = {
            "nonhourly": lambda d: d["Parameters"].update(
                {"Time step (min)": 30}),
            "negative load": lambda d: d["Buses"]["b"].update(
                {"Load (MW)": -1.0}),
            "zero initial status": lambda d: d["Generators"]["g"].update(
                {"Initial status (h)": 0}),
            "fractional uptime": lambda d: d["Generators"]["g"].update(
                {"Minimum uptime (h)": 1.5}),
            "nonconvex cost": lambda d: d["Generators"]["g"].update({
                "Production cost curve (MW)": [0.0, 5.0, 10.0],
                "Production cost curve ($)": [0.0, 10.0, 15.0]}),
            "time-varying curve": lambda d: d["Generators"]["g"].update(
                {"Production cost curve (MW)": [[0.0] * 7, [10.0] * 7]}),
            "decreasing startup cost": lambda d: d["Generators"]["g"].update(
                {"Startup costs ($)": [10.0, 30.0, 20.0]}),
            "wrong first delay": lambda d: d["Generators"]["g"].update(
                {"Startup delays (h)": [2, 3, 5]}),
            "nonspinning reserve": lambda d: d["Reserves"].update(
                {"r": {"Type": "flexiramp", "Amount (MW)": 1.0}}),
            "multiple line outage": lambda d: d["Contingencies"].update(
                {"c": {"Affected lines": ["a", "b"]}}),
        }
        for label, mutate in mutations.items():
            with self.subTest(feature=label):
                data = instance()
                mutate(data)
                with self.assertRaises(AssertionError):
                    generate.check_schema(data, 7)


class TinyNetworkEdgeTests(unittest.TestCase):
    @staticmethod
    def two_bus_instance():
        data = instance(hours=1)
        data["Buses"]["other"] = {"Load (MW)": 0.0}
        data["Transmission lines"]["line"] = {
            "Source bus": "b", "Target bus": "other",
            "Susceptance (S)": 1.0,
            "Normal flow limit (MW)": 10.0,
            "Emergency flow limit (MW)": 10.0,
        }
        return data

    def test_network_with_no_contingencies(self):
        _, info = generate.build(self.two_bus_instance(), 1, "network")
        self.assertEqual(info["eligible_outages"], 0)
        self.assertEqual(info["security_pairs"], 0)
        self.assertIsNone(info["minimum_outage_denominator"])

    def test_base_network_does_not_require_nonislanding_outages(self):
        data = self.two_bus_instance()
        data["Contingencies"]["c"] = {"Affected lines": ["line"]}
        generate.build(data, 1, "network")
        with self.assertRaisesRegex(AssertionError, "Islanding"):
            generate.build(data, 1, "n1")


if __name__ == "__main__":
    unittest.main()
