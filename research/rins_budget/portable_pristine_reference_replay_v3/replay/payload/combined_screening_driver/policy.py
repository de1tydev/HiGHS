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
                         'B': Arm('B', True, True, 'optimized'),
                         'C': Arm('C', False, True, 'optimized')})
DATES = ()
CONFIRMATION = ()  # Pending independent review and exact source reservations.
W1_STATUS = 'excluded_final_parent_decision'
TARGET_MEASUREMENT_RELEASED = False
METRICS = ('solver_process_wall_seconds', 'standalone_equivalent_e2e_seconds')

def arm_record(name):
    if name not in ARMS: raise ValueError('Only frozen A/B/C arms are allowed')
    return asdict(ARMS[name])

def schedule():
    return [{'sequence': i+1, 'case': date, 'seed': seed, 'arm_order': list(order)}
            for i, (date, seed, order) in enumerate(CONFIRMATION)]

def confirmation_gate(pairs):
    return {'passed':False,'reason':'Legacy A/B confirmation gate is disabled; use seed_comparison.advancement_gate with the exact reviewed protocol'}
