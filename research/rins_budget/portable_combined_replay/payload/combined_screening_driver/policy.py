"""Immutable, source-only arm and campaign policy. No numerical imports."""
from dataclasses import asdict, dataclass
from types import MappingProxyType
import statistics

@dataclass(frozen=True)
class Arm:
    name: str
    lp_discovery: bool
    root_credit: bool
    separator_variant: str

ARMS = MappingProxyType({'A': Arm('A', False, False, 'baseline'),
                         'B': Arm('B', True, True, 'optimized')})
DATES = ('2017-02-01', '2017-08-01', '2017-11-01')
CONFIRMATION = (
    ('2017-11-01', 1, 'BA'), ('2017-08-01', 1, 'AB'), ('2017-02-01', 3, 'BA'),
    ('2017-02-01', 4, 'AB'), ('2017-11-01', 2, 'AB'), ('2017-08-01', 2, 'BA'),
    ('2017-08-01', 3, 'AB'), ('2017-02-01', 5, 'BA'), ('2017-11-01', 3, 'BA'))
METRICS = ('solver_process_wall_seconds', 'standalone_equivalent_e2e_seconds')

def arm_record(name):
    if name not in ARMS: raise ValueError('Only frozen A/B arms are allowed')
    return asdict(ARMS[name])

def schedule():
    return [{'sequence': i+1, 'case': date, 'seed': seed, 'arm_order': list(order)}
            for i, (date, seed, order) in enumerate(CONFIRMATION)]

def confirmation_gate(pairs):
    if len(pairs) != len(CONFIRMATION):
        return {'passed': False, 'reason': 'All nine reserved pairs are required'}
    grouped = {date: [] for date in DATES}
    for record, (date, seed, order) in zip(pairs, CONFIRMATION):
        if (record.get('case'), record.get('seed'), record.get('arm_order')) != (date, seed, list(order)):
            return {'passed': False, 'reason': 'Reserved schedule mismatch'}
        comparison = record.get('comparison', {})
        if not comparison.get('valid_comparison'):
            return {'passed': False, 'reason': 'Incomplete or invalid pair; no imputed timing'}
        grouped[date].append(comparison)
    by_date = {}
    for date, comparisons in grouped.items():
        values = {}
        for metric in METRICS:
            reductions = [c['metrics'][metric]['reduction_fraction'] for c in comparisons]
            import math
            valid = all(type(r) in (int, float) and math.isfinite(r) for r in reductions)
            values[metric] = {'paired_reductions': reductions,
                'median_paired_reduction': statistics.median(reductions) if valid else None,
                'passed': valid and min(reductions) > 0 and statistics.median(reductions) >= .30}
        by_date[date] = values
    return {'passed': all(v['passed'] for d in by_date.values() for v in d.values()), 'by_date': by_date}
