"""Pure scheduling state for the fixed tiny: integer seeds stay isolated."""
from copy import deepcopy
import math


class TinySchedule:
    MAX_LP_CALLS = 9
    MAX_LP_ADDITIONS = 8

    def __init__(self, mode):
        if mode not in ('continuous', 'integer', 'both'):
            raise ValueError('Unknown tiny mode')
        self.mode = mode
        self._seeds = []
        self._seen_continuous_names = set()
        self.continuous_calls = 0
        self.continuous_additions = 0
        self.continuous_lower = None
        self.continuous_upper = None
        self._pending_continuous_batch = None

    def _accept_batch(self, batch, lower, upper):
        if not all(isinstance(x, (float, int)) and math.isfinite(x) for x in (lower, upper)):
            raise ValueError('Finite tiny interval required')
        names = batch['names']
        if not names or len(names) != len(set(names)) or self._seen_continuous_names.intersection(names):
            raise ValueError('Duplicate/empty continuous cut names')
        self._seen_continuous_names.update(names)
        self._pending_continuous_batch = deepcopy(batch)
        self.continuous_lower = lower if self.continuous_lower is None else max(self.continuous_lower, lower)
        self.continuous_upper = upper

    def record_seed(self, batch, lower, upper):
        if len(self._seeds) >= 2:
            raise ValueError('Exactly two seed solves are permitted')
        self._accept_batch(batch, lower, upper)
        self._seeds.append((deepcopy(batch), lower))
        self.continuous_calls += 1
        self.continuous_additions = self.continuous_calls-1

    def integer_seed(self):
        if len(self._seeds) != 2:
            raise ValueError('Both integer seed batches are required')
        # Neither subsequent continuous updates nor consumer mutations affect this.
        return deepcopy(tuple(batch for batch, _ in self._seeds)), max(lower for _, lower in self._seeds)

    def continuous_action(self):
        if len(self._seeds) != 2:
            raise ValueError('Finish exactly two seeds first')
        if self.mode == 'integer':
            return 'skip'
        gap = self.continuous_upper-self.continuous_lower
        if gap < -1e-7:
            raise ValueError('Negative continuous interval')
        if gap <= 1e-5:
            return 'closed'
        if self.continuous_calls >= self.MAX_LP_CALLS:
            return 'exhausted'
        return 'continue'

    def continuation_input(self):
        if self.continuous_action() != 'continue' or self.continuous_additions >= self.MAX_LP_ADDITIONS:
            raise ValueError('Continuous continuation is unavailable')
        # The new evaluation index is unique within the continuous master.
        return deepcopy(self._pending_continuous_batch), self.continuous_calls

    def record_continuation(self, batch, lower, upper):
        if self.continuous_action() != 'continue':
            raise ValueError('No continuous solve is pending')
        self._accept_batch(batch, lower, upper)
        self.continuous_calls += 1
        self.continuous_additions += 1

    @staticmethod
    def integer_cut_index(master_index):
        if type(master_index) is not int or not 0 <= master_index < 3:
            raise ValueError('Integer tiny supports at most three masters')
        return 2+master_index
