#!/usr/bin/env python3
"""Exact rational property check; not floating-point or performance evidence."""
from fractions import Fraction as F
from math import floor
import json


def mir_integer(a, f):
    down = floor(a)
    return down + max(F(0), (a - down - f) / (1 - f))


def mir_row(coefficients, continuous, rhs):
    f = rhs - floor(rhs)
    assert 0 < f < 1
    return ([mir_integer(a, f) for a in coefficients],
            [min(F(0), a) / (1 - f) for a in continuous], F(floor(rhs)))


cases = 0
for denominator in range(2, 20):
    for numerator in range(1, denominator):
        for q in range(-16, 17):
            for upper in (0, 1, 2, 7):
                for integral_rhs in (-19, -1, 0, 23):
                    coefficients = [F(q), F(-7, 3), F(0), F(11, 4)]
                    continuous = [F(-3, 5), F(0), F(7, 3)]
                    rhs = integral_rhs + F(numerator, denominator)
                    original = mir_row(coefficients, continuous, rhs)
                    complemented = list(coefficients)
                    complemented[0] = -complemented[0]
                    ints, cont, bound = mir_row(
                        complemented, continuous, rhs - q * upper)
                    # Substitute y = upper - x back into the complemented cut.
                    bound -= ints[0] * upper
                    ints[0] = -ints[0]
                    assert (ints, cont, bound) == original
                    cases += 1
for f in (F(1, 200), F(199, 200)):
    for q in (-8, -1, 0, 1, 8):
        for upper in (0, 1, 7):
            original = mir_row([F(q), F(3, 4)], [F(-1, 4)], f)
            ints, cont, bound = mir_row(
                [F(-q), F(3, 4)], [F(-1, 4)], f - q * upper)
            bound -= ints[0] * upper
            ints[0] = -ints[0]
            assert (ints, cont, bound) == original
            cases += 1
print(json.dumps({"status": "PASS", "exact_rational_cases": cases,
                  "floating_identity_claim": False,
                  "performance_claim": False}, sort_keys=True))
