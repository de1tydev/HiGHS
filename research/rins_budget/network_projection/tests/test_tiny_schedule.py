"""Optimizer-free regression for the actual fixed-fixture replay controller."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from tiny_schedule import TinySchedule


def batch(index):
    return {'names':[f'network_cut_{index}_0', f'network_cut_{index}_1'],
            'value':[float(index), -1.]}


class TinyScheduleTests(unittest.TestCase):
    def test_known_open_seeds_and_independent_continuous_progress(self):
        # Recorded fixed triangle: the two seed lower bounds are 42 and ~63,
        # whereas the explicit full reference is 1540.5. Seeding is not closure.
        integer = TinySchedule('integer')
        both = TinySchedule('both')
        for state in (integer, both):
            state.record_seed(batch(0), 42., 4000.)
            state.record_seed(batch(1), 62.999999999999964, 3000.)
        initial, baseline = both.integer_seed()
        self.assertEqual(integer.continuous_action(), 'skip')
        self.assertEqual(both.continuous_action(), 'continue')
        self.assertEqual(baseline, 62.999999999999964)
        with self.assertRaises(ValueError):integer.continuation_input()
        names = set(initial[0]['names']+initial[1]['names'])
        for expected_index, lower, upper in [(2, 900., 2000.), (3, 1540.499999999997, 1540.5000000000366)]:
            pending, index = both.continuation_input()
            self.assertEqual(index, expected_index)
            new = batch(index)
            self.assertFalse(names.intersection(new['names']))
            names.update(new['names'])
            both.record_continuation(new, lower, upper)
        self.assertEqual(both.continuous_action(), 'closed')
        self.assertEqual((both.continuous_calls,both.continuous_additions),(4,3))
        self.assertEqual(both.integer_seed(),(initial,baseline))
        # A consumer cannot mutate the retained seed state through returned copies.
        copied,_ = both.integer_seed();copied[0]['value'][0] = -999.
        self.assertEqual(both.integer_seed(),(initial,baseline))
        self.assertEqual([both.integer_cut_index(i) for i in range(3)],[2,3,4])
        with self.assertRaises(ValueError):both.record_seed(batch(8),0.,1.)
        with self.assertRaises(ValueError):both.continuation_input()

        capped=TinySchedule('continuous')
        capped.record_seed(batch(0),42.,4000.)
        capped.record_seed(batch(1),63.,3000.)
        while capped.continuous_action() == 'continue':
            _,index=capped.continuation_input()
            capped.record_continuation(batch(index),63.,3000.)
        self.assertEqual(capped.continuous_action(),'exhausted')
        self.assertEqual((capped.continuous_calls,capped.continuous_additions),(9,8))
        with self.assertRaises(ValueError):capped.continuation_input()
        with self.assertRaises(ValueError):capped.record_continuation(batch(9),1540.5,1540.5)
        self.assertEqual(capped.integer_seed()[1],63.)

if __name__=='__main__':unittest.main()
