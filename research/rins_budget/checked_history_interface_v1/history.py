"""Receipt-bound labels and frozen past-only retrieval; no optimization calls."""
from __future__ import annotations
from dataclasses import dataclass
import datetime as dt
import math
from pathlib import Path
import sys
import time

from common import HERE, check_point, checked_member, digest, expected_model, read_json, require, sha

sys.path.insert(0, str(HERE.parent / 'generalization_20261006'))
from history_start import propose as old_propose

_ADMITTED = object()


def utc(value):
    result = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
    require(result.tzinfo is not None, 'Timezone required')
    return result.astimezone(dt.timezone.utc)


@dataclass(frozen=True)
class Label:
    record: dict
    admission: object
    record_digest: str = ''


def admit_synthetic(path):
    """Test-scope only: independently recheck bound model/point, never trust flags."""
    path = Path(path).resolve()
    raw = read_json(path)
    require(raw['schema'] == 'enumerated-binary-test-label/v1', 'Synthetic schema required')
    require(raw['scope'] == 'synthetic_test', 'Synthetic label scope')
    src = checked_member(path.parent, raw['expected']['path'], raw['expected']['sha256'])
    point = checked_member(path.parent, raw['point']['path'], raw['point']['sha256'])
    e, p = expected_model(src), read_json(point)
    require(p['columns'] == e['col_names'], 'Point column order')
    require(check_point(e, p['values'])['passed'], 'Synthetic original matrix failed')
    require(all(type(v) in (int, float) and math.isfinite(v) and v in (0, 1) for v in p['values']), 'Literal binary test point required')
    require(all(int(v) == 1 for v in e['integrality']), 'Only all-binary test labels')
    require(raw['feature_spec'] == 'two-period-demand-identity/v1' and e['num_row'] == 3, 'Frozen test features required')
    require(raw['feature'] == [float(v) for v in e['row_lower'][:2]], 'Test features differ from source model')
    require(utc(raw['start']) < utc(raw['end']), 'Invalid label window')
    require(utc(raw['end']) <= utc(raw['observed_available_at']), 'Observed availability precedes window')
    require(raw['scope'] == raw.get('feature_scope', raw['scope']), 'Feature scope mismatch')
    record = {k: raw[k] for k in ('scope', 'case', 'start', 'end', 'observed_available_at', 'feature_spec', 'feature', 'topology')}
    record.update(id=sha(path), source_sha256=raw['expected']['sha256'], columns=list(e['col_names']),
                  u=[int(v) for v in p['values']], evidence_sha256=digest({'label': sha(path), 'source': sha(src), 'point': sha(point)}))
    return Label(record, _ADMITTED, digest(record))


def predict(query, labels, *, method='consensus', k=3):
    """Use observed chronology only. Retrospective replay is deliberately absent."""
    started = time.monotonic()
    require(query['mode'] == 'observed', 'Simulated historical availability needs a separately frozen runner')
    cutoff = utc(query['start'])
    require(utc(query['features_available_at']) <= cutoff, 'Late query features')
    require(query['scope'] in ('synthetic_test', 'scuc_checked'), 'Unknown query scope')
    require(query['columns'] and len(set(query['columns'])) == len(query['columns']), 'Query columns')
    require(query['feature'] and all(type(v) in (int, float) and math.isfinite(v) for v in query['feature']), 'Nonfinite query feature')
    accepted, excluded, groups = [], [], {}
    for item in labels:
        require(isinstance(item, Label) and item.admission is _ADMITTED, 'Unverified label object')
        require(digest(item.record) == item.record_digest, 'Admitted label mutated')
        row = item.record
        key = (row['case'], row['topology'], utc(row['start']), utc(row['end']))
        groups.setdefault(key, []).append(row)
    for group in groups.values():
        if len({row['source_sha256'] for row in group}) != 1:
            excluded.extend(dict(id=row['id'], reason='conflicting_window_source') for row in group)
            continue
        group.sort(key=lambda row: (utc(row['observed_available_at']), row['id']))
        row = group[0]
        excluded.extend(dict(id=x['id'], reason='duplicate_window') for x in group[1:])
        if utc(row['end']) > cutoff or utc(row['observed_available_at']) > cutoff:
            excluded.append(dict(id=row['id'], reason='future_overlapping_or_late_label'))
            continue
        if any(row[key] != query[key] for key in ('scope', 'case', 'topology', 'feature_spec', 'columns')):
            excluded.append(dict(id=row['id'], reason='incompatible_feature_or_binary_contract'))
            continue
        require(len(row['feature']) == len(query['feature']), 'Feature dimension mismatch')
        accepted.append(dict(row, checked=True, label_available=row['observed_available_at']))
    result = old_propose(query, accepted, method, k)
    result['excluded'] = excluded + result['excluded']
    result.update(prediction_seconds=time.monotonic() - started, label_admission='verified_artifacts_only',
                  eligible_distinct_windows=len(accepted), chronology='observed_wall_clock', query_sha256=digest(query))
    return result
