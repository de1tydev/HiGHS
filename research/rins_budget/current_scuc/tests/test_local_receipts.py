"""Tiny local I/O tests. No native invocation, model, or numerical dependency."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from current_scuc import receipts


class LocalReceiptsTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='scuc-local-receipts-')
        self.addCleanup(self.temporary.cleanup)
        self.run = Path(self.temporary.name).resolve()
        self.source = 'a'*64
        self.deadline = time.monotonic()+60
        self.reference = {'schema': receipts.SOURCE_SCHEMA, 'source_manifest_sha256': self.source}
        self.limits = patch.object(receipts.resource, 'getrlimit', return_value=(512*1024**2,)*2)
        self.limits.start()
        self.addCleanup(self.limits.stop)
        self.checkpoints = receipts.Checkpoints(self.run, self.reference, self.deadline)

    def snapshot(self, number, trace=None):
        path = self.run/f'state-{number:02d}.json'
        path.write_text(json.dumps(dict(run_directory=str(self.run), source_manifest_sha256=self.source,
                                       trace=trace or [])))
        return receipts.Artifact('state_snapshot', path)

    def seal(self, number=1, artifacts=None, **kwargs):
        return self.checkpoints.seal(point_id=kwargs.get('point_id', 'seed'),
            stage_kind=kwargs.get('stage_kind', 'post_native_solve'),
            state=kwargs.get('state', 'unvalidated'),
            artifacts=artifacts or [self.snapshot(number)], measurements={},
            cleanup_receipt={'cleanup_verified': True})

    def test_local_seal_has_no_data_copy_and_chains(self):
        data = self.run/'payload.txt'
        data.write_bytes(b'finished native output\n')
        inode = data.stat().st_ino
        first = self.seal(artifacts=[self.snapshot(1), receipts.Artifact('native_output', data)])
        verified = receipts.verify_receipt(first, self.run, self.source, self.deadline)
        self.assertEqual(data.stat().st_ino, inode)
        self.assertEqual(data.stat().st_mode & 0o222, 0)
        self.assertEqual({p.name for p in Path(first).parent.iterdir()}, {'manifest.json', 'local-receipt.json'})
        self.assertEqual(verified['receipt']['durability'], 'LOCAL_FSYNC_HASH')
        self.assertNotIn('archive_sha256', verified['receipt'])
        self.seal(2, artifacts=[self.snapshot(2), receipts.Artifact('native_output', data)])
        chain = receipts.verify_run(self.run, self.source, self.deadline)
        self.assertEqual(len(chain), 2)
        self.assertEqual(chain[1]['receipt']['prior_receipts'][0]['sha256'],
                         verified['metadata_files_sha256'][first])

    def test_same_length_artifact_mutation_fails(self):
        data = self.run/'payload.txt'
        data.write_bytes(b'first')
        first = self.seal(artifacts=[self.snapshot(1), receipts.Artifact('payload', data)])
        data.chmod(0o600)
        data.write_bytes(b'other')
        data.chmod(0o400)
        with self.assertRaisesRegex(ValueError, 'identity|hash'):
            receipts.verify_receipt(first, self.run, self.source, self.deadline)

    def test_replaced_equal_bytes_are_not_original_inode(self):
        artifact = self.snapshot(1)
        first = self.seal(artifacts=[artifact])
        path = Path(artifact.path)
        replacement = path.with_suffix('.replacement')
        replacement.write_bytes(path.read_bytes())
        replacement.chmod(0o400)
        replacement.replace(path)
        with self.assertRaisesRegex(ValueError, 'identity'):
            receipts.verify_receipt(first, self.run, self.source, self.deadline)

    def test_mutable_state_and_retry_are_rejected(self):
        mutable = self.run/'STATE.json'
        mutable.write_text('{}')
        with self.assertRaisesRegex(ValueError, 'mutable STATE'):
            self.seal(artifacts=[self.snapshot(1), receipts.Artifact('state', mutable)])
        self.assertTrue((self.run/'local-checkpoint-failure.json').exists())
        with self.assertRaisesRegex(ValueError, 'failure is terminal'):
            self.seal(2)

    def test_symlink_and_remote_schema_rejected(self):
        actual = self.run/'actual'
        actual.write_text('{}')
        link = self.run/'alias'
        link.symlink_to(actual)
        with self.assertRaisesRegex(ValueError, 'symlink'):
            receipts.inside(link, self.run)
        with self.assertRaisesRegex(ValueError, 'remote archival'):
            receipts.validate_source_reference({**self.reference, 'library_file_id': 'unused'})

    def test_duplicate_keys_and_nonfinite_metadata_rejected(self):
        path = self.run/'duplicate.json'
        path.write_text('{"same":1,"same":2}')
        with self.assertRaisesRegex(ValueError, 'duplicate JSON'):
            receipts.read(path)
        path.write_text('{"value":NaN}')
        with self.assertRaisesRegex(ValueError, 'nonfinite'):
            receipts.read(path)

    def test_deadline_and_wrong_source_rejected(self):
        path = self.seal()
        with self.assertRaisesRegex(ValueError, 'foreign run/index/source'):
            receipts.verify_receipt(path, self.run, 'b'*64, self.deadline)
        with self.assertRaises(TimeoutError):
            receipts.verify_receipt(path, self.run, self.source, time.monotonic()-1)

    def test_missing_sequence_and_partial_stage_rejected(self):
        self.seal()
        stage = self.run/'durability'/'checkpoint-03'
        stage.mkdir()
        with self.assertRaisesRegex(ValueError, 'sequence'):
            receipts.verify_run(self.run, self.source, self.deadline)

    def test_checked_binding_requires_exact_stage_row_and_bytes(self):
        rd = self.run/'mip-01'
        rd.mkdir()
        artifacts = []

        def record(name):
            path = rd/name
            path.write_text('tiny fixture '+name)
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            artifacts.append(receipts.Artifact('file_'+str(len(artifacts)), path, digest))
            return {'path': str(path), 'sha256': digest}

        row = {key: {} for key in receipts._CHECKED_ROW_KEYS}
        row.update(call=1, role='discovery')
        for key, filename in [('model', 'master.mps'), ('expected', 'expected.json'),
                              ('api_report', 'api.json'), ('row_sidecar', 'rows.json')]:
            item = record(filename)
            row['master_identity'].update({key+'_path': item['path'], key+'_sha256': item['sha256']})
        record('solution.sol')
        for key in ('options', 'readback'):
            item = record(key+'.json')
            row['options_artifacts'].update({key+'_path': item['path'], key+'_sha256': item['sha256']})
        for key in ('adaptive_support_artifact', 'stored_lift_artifact', 'oracle_artifact',
                    'full_source_quality_artifact', 'source_quality_artifact'):
            item = record(key+'.json')
            row['evaluation'][key] = {'document': {**item, 'path': Path(item['path']).name}}
        artifacts.append(self.snapshot(1, [row]))
        path = self.seal(artifacts=artifacts, point_id='mip-01', stage_kind='post_full_check', state='validated')
        binding = receipts.bind_checked_stage(path, self.run, 1, self.source, row)
        self.assertTrue(binding['bytes_reread'])
        self.assertEqual(len(binding['checked_point_files_sha256']), 12)
        changed = copy.deepcopy(row)
        changed['report'] = {'changed': True}
        with self.assertRaisesRegex(ValueError, 'differs from checked STATE'):
            receipts.bind_checked_stage(path, self.run, 1, self.source, changed)
        with self.assertRaisesRegex(ValueError, 'not this call'):
            receipts.bind_checked_stage(path, self.run, 2, self.source, row)

    def test_whole_storage_threshold_is_fixed(self):
        value = {'path': str(self.run), 'device': 1, 'block_bytes': 4096,
                 'available_bytes': receipts.WHOLE_STORAGE_REQUIRED-1}
        with patch.object(receipts.budget, 'filesystem', return_value=value):
            with self.assertRaises(receipts.budget.StorageAdmissionError):
                receipts.admit_whole(self.run)
        self.assertEqual(receipts.WHOLE_STORAGE_REQUIRED, 11 * 1024**3)


if __name__ == '__main__':
    unittest.main()
