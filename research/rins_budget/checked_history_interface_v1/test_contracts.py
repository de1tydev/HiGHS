"""Artifact/admission contracts; authoring these tests does not authorize a run."""
import datetime as dt
import itertools
import json
import math
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common import check_point, expected_model, read_json, read_values, sha, write_json, write_values
from history import Label, admit_synthetic, predict
import driver
from current_scuc.core.canonical_mps_export import export_v2 as exporter


def fixture(root, name='sample', demands=(2, 2), *, day=1, window=None,
            available=None, feature_spec='two-period-demand-identity/v1', feature=None, point=None):
    """Write canonical model/point/label/query files and enumerate 16 test assignments."""
    root = Path(root) / name
    root.mkdir()
    source = SimpleNamespace(names=['u0', 'u1', 'u2', 'u3'], lb=[0]*4, ub=[1]*4,
        obj=[3, 5, 3, 5], binary=[True]*4, rhs=[*demands, 0], sense=['G', 'G', 'L'],
        ri=[0, 0, 1, 1, 2, 2], ci=[0, 1, 2, 3, 0, 2], val=[2, 3, 2, 3, 1, -1])
    e = exporter.intended_model(source)
    model_path, expected_path = root / 'original.mps', root / 'expected.json'
    exporter.write_model(source, model_path, expected=e)
    raw = {k: v.tolist() if hasattr(v, 'tolist') else v for k, v in e.items()}
    for key in ('col_lower', 'col_upper', 'row_lower', 'row_upper'):
        raw[key] = ['+inf' if v == math.inf else '-inf' if v == -math.inf else v for v in raw[key]]
    write_json(expected_path, raw)
    feasible = []
    for values in itertools.product((0, 1), repeat=4):
        if check_point(e, values)['passed']:
            feasible.append((sum(c*v for c, v in zip(source.obj, values)), values))
    if not feasible:
        raise ValueError('Fixture has no feasible binary assignment')
    optimum, best = min(feasible)
    values = list(best if point is None else point)
    point_path, label_path = root / 'point.json', root / 'label.json'
    write_json(point_path, dict(columns=source.names, values=values))
    start = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc) + dt.timedelta(days=day-1)
    start, end = window or (start.isoformat(), (start + dt.timedelta(hours=2)).isoformat())
    label = dict(schema='enumerated-binary-test-label/v1', scope='synthetic_test',
        case='two-period-test', topology='four-binary-two-period/v1', start=start, end=end,
        observed_available_at=available or end, feature_spec=feature_spec,
        feature=list(demands) if feature is None else feature,
        expected=dict(path=expected_path.name, sha256=sha(expected_path)),
        point=dict(path=point_path.name, sha256=sha(point_path)), enumerated_assignments=16)
    write_json(label_path, label)
    query = dict(mode='observed', scope=label['scope'], case=label['case'], topology=label['topology'],
        start='2030-01-01T00:00:00Z', features_available_at='2029-12-31T23:59:00Z',
        feature_spec='two-period-demand-identity/v1', feature=list(demands), columns=list(source.names))
    query_path = root / 'query.json'
    write_json(query_path, query)
    return dict(model=model_path, expected=expected_path, point=point_path, label=label_path,
                values=values, query=query, query_path=query_path, source=source, optimal_objective=optimum)


class Contracts(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def make(self, name, **kwargs):
        return fixture(self.root, name, **kwargs)

    def test_canonical_fixture_roundtrip_and_consensus(self):
        rows = [self.make(str(i), day=i+1) for i in range(3)]
        f = rows[0]
        raw = read_json(f['expected'])
        self.assertEqual(raw['row_upper'], ['+inf', '+inf', 0.0])
        self.assertEqual(raw['row_lower'], [2.0, 2.0, '-inf'])
        self.assertNotIn('checked', read_json(f['label']))
        checked = check_point(expected_model(f['expected']), f['values'])
        self.assertTrue(checked['passed'])
        self.assertFalse(checked['full_scuc_checked'])
        result = predict(f['query'], [admit_synthetic(x['label']) for x in rows])
        self.assertEqual(result['suggestions'], dict(zip(f['source'].names, f['values'])))
        self.assertFalse(result['feasibility_certified'])
        self.assertIsNone(result['lower_bound'])

    def test_tampered_expected_or_point_rejected(self):
        for key in ('expected', 'point'):
            with self.subTest(key=key):
                f = self.make(key)
                with f[key].open('ab') as stream:
                    stream.write(b'\n')
                with self.assertRaisesRegex(ValueError, 'Changed artifact'):
                    admit_synthetic(f['label'])

    def test_invalid_points_rejected_even_with_matching_hash(self):
        for i, point in enumerate(([0]*4, [1, .5, 1, .5], [True]*4, [1, 0, 1, 1e-7], [1])):
            with self.subTest(point=point):
                with self.assertRaises(ValueError):
                    admit_synthetic(self.make(str(i), point=point)['label'])

    def test_caller_checked_flag_cannot_admit_label(self):
        f = self.make('forged')
        raw = dict(read_json(f['label']), checked=True, u=f['values'])
        for forged in (raw, Label(raw, object())):
            with self.assertRaisesRegex(ValueError, 'Unverified label object'):
                predict(f['query'], [forged])

    def test_duplicate_windows_collapse_before_k3(self):
        a, b, c = (self.make(n, day=d) for n, d in (('a', 1), ('b', 1), ('c', 2)))
        result = predict(a['query'], [admit_synthetic(x['label']) for x in (a, b, c)])
        self.assertEqual(result['eligible_distinct_windows'], 2)
        self.assertEqual(result['suggestions'], {})
        self.assertIn('duplicate_window', [x['reason'] for x in result['excluded']])

    def test_admitted_nested_values_and_times_cannot_mutate(self):
        f = self.make('mutation')
        mutations = (lambda r: r['u'].__setitem__(0, 1-r['u'][0]),
                     lambda r: r['feature'].__setitem__(0, r['feature'][0]+1),
                     lambda r: r.__setitem__('observed_available_at', '2017-01-01T00:00:00Z'))
        for mutate in mutations:
            label = admit_synthetic(f['label'])
            mutate(label.record)
            with self.assertRaisesRegex(ValueError, 'Admitted label mutated'):
                predict(f['query'], [label], method='nearest')

    def test_equivalent_utc_encodings_count_as_one_window(self):
        encodings = [('2026-01-01T00:00:00Z', '2026-01-01T02:00:00Z'),
                     ('2026-01-01T00:00:00+00:00', '2026-01-01T02:00:00+00:00'),
                     ('2026-01-01T01:00:00+01:00', '2026-01-01T03:00:00+01:00')]
        rows = [self.make(str(i), window=window) for i, window in enumerate(encodings)]
        result = predict(rows[0]['query'], [admit_synthetic(row['label']) for row in rows])
        self.assertEqual(result['eligible_distinct_windows'], 1)
        self.assertEqual(result['suggestions'], {})
        self.assertEqual([row['reason'] for row in result['excluded']], ['duplicate_window']*2)

    def test_conflicting_source_revisions_reject_entire_window(self):
        a, b = self.make('a'), self.make('b', demands=(3, 3))
        result = predict(a['query'], [admit_synthetic(x['label']) for x in (a, b)], method='nearest')
        self.assertEqual(result['eligible_distinct_windows'], 0)
        self.assertEqual(result['suggestions'], {})
        self.assertEqual([x['reason'] for x in result['excluded']], ['conflicting_window_source']*2)

    def test_future_overlap_and_late_availability_excluded(self):
        cases = [dict(window=('2031-01-01T00:00:00Z', '2031-01-01T02:00:00Z')),
                 dict(window=('2029-12-31T23:00:00Z', '2030-01-01T01:00:00Z')),
                 dict(available='2030-01-01T00:00:01Z')]
        for i, options in enumerate(cases):
            f = self.make(str(i), **options)
            result = predict(f['query'], [admit_synthetic(f['label'])], method='nearest')
            self.assertEqual(result['suggestions'], {})
            self.assertEqual(result['excluded'][0]['reason'], 'future_overlapping_or_late_label')

    def test_feature_order_and_point_column_order_rejected(self):
        f = self.make('feature', demands=(2, 3), feature=[3, 2])
        with self.assertRaisesRegex(ValueError, 'features differ'):
            admit_synthetic(f['label'])
        f = self.make('columns')
        p = read_json(f['point']); p['columns'].reverse()
        f['point'].write_text(json.dumps(p))
        raw = read_json(f['label']); raw['point']['sha256'] = sha(f['point'])
        f['label'].write_text(json.dumps(raw))
        with self.assertRaisesRegex(ValueError, 'Point column order'):
            admit_synthetic(f['label'])

    def test_query_feature_spec_and_columns_must_match(self):
        f = self.make('query'); label = admit_synthetic(f['label'])
        for change in (dict(feature_spec='reordered/v1'), dict(columns=list(reversed(f['source'].names)))):
            result = predict(dict(f['query'], **change), [label], method='nearest')
            self.assertEqual(result['suggestions'], {})
            self.assertEqual(result['excluded'][0]['reason'], 'incompatible_feature_or_binary_contract')

    def test_two_agreeing_labels_still_abstain(self):
        a, b = self.make('a'), self.make('b', day=2)
        result = predict(a['query'], [admit_synthetic(x['label']) for x in (a, b)])
        self.assertEqual(result['suggestions'], {})
        self.assertEqual(len(result['neighbors']), 2)
        self.assertEqual(set(result['vote_fraction'].values()), {1.0})

    def test_named_vector_roundtrip_and_duplicate_rejection(self):
        path = self.root / 'vector.txt'; names = ['u0', 'u1']
        write_values(path, names, [1, 1e-8])
        self.assertEqual(read_values(path, names), [1, 1e-8])
        path.write_text('u0 1\nu0 0\n')
        with self.assertRaisesRegex(ValueError, 'duplicate point row'):
            read_values(path, names)

    def test_cold_final_source_contract(self):
        controller = (HERE / 'driver.py').read_text()
        native = (HERE / 'sparse_probe.cpp').read_text()
        self.assertIn("str(point_input) if point_input else '-'", controller)
        self.assertIn("native('final', start, allocation)", controller)
        self.assertRegex(native, r'if \(mode == "final" && std::string\(argv\[2\]\) != "-"\)\s*\{\s*require\(index.size\(\) == size_t\(n\)')

    def test_integrity_failure_never_launches_final(self):
        f = self.make('integrity')
        def failed_process(command, out, stage, allocation):
            write_json(Path(command[4]), dict(mode=stage, model_fields_verified=False))
            return dict(hard_watchdog_killed=False, runner_returncode=1)
        with (patch.object(driver, 'limits'), patch.object(driver, 'health'),
              patch.object(driver.envelope, 'STOP_REASON', None),
              patch.object(driver.time, 'monotonic', return_value=100.),
              patch.object(driver.readback, 'verify_expected', return_value={'passed': True}),
              patch.object(driver, 'run_process', side_effect=failed_process) as runner):
            result = driver.run_case(f['model'], f['expected'], f['model'], f['model'],
                f['query_path'], [f['label']], self.root / 'out', method='nearest')
        self.assertFalse(result['passed'])
        self.assertIn('Native model fidelity failed', result['error'])
        self.assertEqual(runner.call_count, 1)
        self.assertEqual(runner.call_args.args[2], 'probe')
        self.assertEqual([call['stage'] for call in result['calls']], ['probe'])


if __name__ == '__main__':
    unittest.main()
