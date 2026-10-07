"""Pure, necessary-only advice screen. No model loader or optimizer calls."""

from collections.abc import Sequence
from dataclasses import dataclass
from fractions import Fraction
from typing import Literal


ExactNumber = int | float | str | Fraction
SUPPORTED_SCOPE = "complete_system_shared_capacity_v1"


@dataclass(frozen=True)
class UnitBounds:
    """Current Pmax and u upper bounds; None hints leave u free at its upper."""

    name: str
    pmax: Sequence[ExactNumber]
    commitment_upper: Sequence[ExactNumber]
    hints: Sequence[int | None]


@dataclass(frozen=True)
class HourAssessment:
    hour_zero_based: int
    possible_capacity: Fraction
    required_capacity: Fraction
    deficit: Fraction
    feasibility_allowance: Fraction

    @property
    def violates(self) -> bool:
        return self.deficit > self.feasibility_allowance


@dataclass(frozen=True)
class Assessment:
    status: Literal["abstain", "retain_unknown", "unsupported"]
    reason: str
    hours: tuple[HourAssessment, ...] = ()

    @property
    def violating_hours(self) -> tuple[int, ...]:
        return tuple(h.hour_zero_based for h in self.hours if h.violates)

    @property
    def network_feasibility(self) -> str:
        return "unknown"


def _number(value: ExactNumber, label: str) -> Fraction:
    # Fraction(float) preserves the actual binary64 value; decimal strings
    # preserve the exact decimal/rational value. Never round either silently.
    if isinstance(value, bool) or not isinstance(value, (int, float, str, Fraction)):
        raise ValueError(f"{label}: expected an integer, finite float, string or Fraction")
    try:
        result = Fraction(value)
    except (ValueError, ZeroDivisionError, OverflowError) as exc:
        raise ValueError(f"{label}: malformed or nonfinite number") from exc
    if result < 0:
        raise ValueError(f"{label}: negative value unsupported")
    return result


def _sequence(values: Sequence, horizon: int, label: str) -> Sequence:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise ValueError(f"{label}: expected a sequence")
    if len(values) != horizon:
        raise ValueError(f"{label}: expected exactly {horizon} entries")
    return values


def _numbers(values: Sequence, horizon: int, label: str) -> tuple[Fraction, ...]:
    return tuple(_number(v, f"{label}[{t}]")
                 for t, v in enumerate(_sequence(values, horizon, label)))


def assess_adequacy(
    *,
    horizon: int,
    units: Sequence[UnitBounds],
    load: Sequence[ExactNumber],
    hard_reserve: Sequence[ExactNumber],
    scope: str,
    complete_scope: bool,
    hard_zero_load_shedding: bool,
    hard_zero_reserve_shortfall: bool,
    feasibility_allowance: Sequence[ExactNumber] | None = None,
) -> Assessment:
    """Reject an advice block only when a generous capacity bound is too low.

    The caller attests to complete current system data and shared capacity:
      p[g,t] + sum_k r[k,g,t] <= Pmax[g,t] * u[g,t],
      sum_g p[g,t] >= load[t], sum_g,k r[k,g,t] >= hard_reserve[t].
    All supply and simultaneous, additive reserve requirements must be covered.
    Shedding and reserve-shortfall variables must be hard-fixed to zero.
    Each u lies in [0, commitment_upper] within [0,1]; hints fix it to 0 or 1.

    Optional allowance[t] is a caller-justified upper bound on the TOTAL MW
    discrepancy allowed in this aggregated inequality, including all relevant
    row, bound and integrality residuals. It is NOT a per-row solver tolerance.
    Omitted allowance means exact arithmetic and exact feasibility semantics.
    Unknown/invalid contracts return unsupported, never an infeasibility claim.
    A retained block still has unknown dispatch, temporal and network feasibility.
    """
    if not isinstance(scope, str) or scope != SUPPORTED_SCOPE:
        return Assessment("unsupported", "Unsupported shared-capacity system scope")
    if complete_scope is not True:
        return Assessment("unsupported", "Complete current supply, load and reserve scope is required")
    if hard_zero_load_shedding is not True or hard_zero_reserve_shortfall is not True:
        return Assessment("unsupported", "Load shedding and reserve shortfall must both be hard-zero")
    try:
        if type(horizon) is not int or horizon <= 0:
            raise ValueError("horizon: expected a positive integer")
        loads = _numbers(load, horizon, "load")
        reserves = _numbers(hard_reserve, horizon, "hard_reserve")
        allowances = ((Fraction(0),) * horizon if feasibility_allowance is None
                      else _numbers(feasibility_allowance, horizon, "feasibility_allowance"))
        if isinstance(units, (str, bytes)) or not isinstance(units, Sequence):
            raise ValueError("units: expected a complete sequence of UnitBounds")
        capacity = [Fraction(0) for _ in range(horizon)]
        names = set()
        for unit in units:
            if not isinstance(unit, UnitBounds):
                raise ValueError("units: expected UnitBounds entries")
            if not isinstance(unit.name, str) or not unit.name.strip() or unit.name in names:
                raise ValueError("units: names must be nonempty and unique")
            names.add(unit.name)
            maxima = _numbers(unit.pmax, horizon, f"{unit.name}.pmax")
            uppers = _numbers(unit.commitment_upper, horizon, f"{unit.name}.commitment_upper")
            hints = _sequence(unit.hints, horizon, f"{unit.name}.hints")
            for t, (maximum, upper, hint) in enumerate(zip(maxima, uppers, hints)):
                if upper > 1:
                    raise ValueError(f"{unit.name}.commitment_upper[{t}]: outside [0,1]")
                if hint is not None:
                    if type(hint) is not int or hint not in (0, 1):
                        raise ValueError(f"{unit.name}.hints[{t}]: expected None, 0 or 1")
                    if hint > upper:
                        raise ValueError(f"{unit.name}.hints[{t}]: conflicts with current upper bound")
                    upper = min(upper, Fraction(hint))
                capacity[t] += maximum * upper
    except ValueError as exc:
        # Validate all entries before producing any mathematical conclusion.
        return Assessment("unsupported", str(exc))

    hours = tuple(HourAssessment(t, capacity[t], loads[t] + reserves[t],
                                 loads[t] + reserves[t] - capacity[t], allowances[t])
                  for t in range(horizon))
    if any(hour.violates for hour in hours):
        return Assessment("abstain", "Aggregate capacity deficit exceeds the supplied allowance", hours)
    return Assessment("retain_unknown", "Necessary aggregate screen only; feasibility remains unknown", hours)
