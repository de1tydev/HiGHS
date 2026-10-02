"""Version-only lazy-extras regression tests. Fake files and mocked processes only."""
from pathlib import Path
import subprocess
from unittest.mock import Mock, patch
import prepare_replay as prepare
from portable_runtime import BindingError, sha
from test_portable_runtime import TemporaryTests

class VersionLoaderTests(TemporaryTests):
    def setUp(self):
        super().setUp()
        self.main = self.root/'libhighs.so.1.15.1'; self.main.write_text('main bytes')
        self.alias = self.root/'libhighs.so.1'; self.alias.symlink_to(self.main.name)
        self.extras = self.root/'libhighs_extras.so'; self.extras.write_text('extras bytes')
        self.value = {'library':str(self.main), 'extras':str(self.extras),
                      'runtime_library_pins':{str(self.main):sha(self.main), str(self.extras):sha(self.extras)}}
        self.main_log = '123: calling init: '+str(self.alias)+'\n'
        self.extras_log = '123: calling init: '+str(self.extras)+'\n'

    def test_lazy_extras_absence_accepted_only_as_unobserved(self):
        result = prepare.validate_version_loader(self.main_log,self.value)
        self.assertEqual(result['main'],[str(self.alias)])
        self.assertEqual(result['extras'],[])
        self.assertEqual(result['extras_observation'],'not_initialized_by_version_command')
        self.assertIn('Actual LP/MIP processes still require',result['scope'])

    def test_correct_present_extras_accepted(self):
        result = prepare.validate_version_loader(self.main_log+self.extras_log,self.value)
        self.assertEqual(result['extras_observation'],'initialized_exact')
        self.assertEqual(result['extras'],[str(self.extras)])

    def test_wrong_present_extras_rejected_even_with_identical_bytes(self):
        other = self.root/'other';other.mkdir()
        wrong = other/self.extras.name;wrong.write_bytes(self.extras.read_bytes())
        with self.assertRaises(BindingError):
            prepare.validate_version_loader(self.main_log+'calling init: '+str(wrong)+'\n',self.value)

    def test_wrong_main_and_missing_main_rejected(self):
        other = self.root/'other';other.mkdir()
        wrong = other/self.alias.name;wrong.write_bytes(self.main.read_bytes())
        for log in ('',self.extras_log,'calling init: '+str(wrong)+'\n'+self.extras_log):
            with self.subTest(log=log),self.assertRaises(BindingError):
                prepare.validate_version_loader(log,self.value)

    def test_duplicate_or_conflicting_alias_initializations_rejected(self):
        logs = [self.main_log*2,self.main_log+'calling init: '+str(self.main)+'\n',
                self.main_log+self.extras_log*2]
        other = self.root/'libhighs.so.foreign';other.write_text('wrong bytes')
        logs.append(self.main_log+'calling init: '+str(other)+'\n')
        for log in logs:
            with self.subTest(log=log),self.assertRaises(BindingError):
                prepare.validate_version_loader(log,self.value)

    def test_whitespace_bearing_observed_provider_cannot_look_absent(self):
        logs = [self.main_log+'calling init: /unexpected path/libhighs_extras.so\n',
                'calling init: /unexpected path/libhighs.so.1\n',
                self.main_log+self.extras_log.rstrip('\n')+' \n',
                'calling init: '+str(self.alias)+' \n']
        for log in logs:
            with self.subTest(log=log),self.assertRaises(BindingError):
                prepare.validate_version_loader(log,self.value)

    def test_same_path_changed_provider_bytes_rejected(self):
        for path in (self.main,self.extras):
            original = path.read_bytes();path.write_bytes(original+b'changed')
            with self.subTest(path=path.name),self.assertRaises(BindingError):
                prepare.validate_version_loader(self.main_log+self.extras_log,self.value)
            path.write_bytes(original)

    def test_actual_solver_guard_still_requires_loaded_extras(self):
        from test_contract import BoundTests
        witness = BoundTests()
        # Use the inherited solver report helper; omitting extras cannot become valid.
        from contracts import LIBRARY
        report = witness.report('calling init: '+str(LIBRARY)+'\nSolving report\n  Model master\n  Status Optimal\n  Dual bound 99.5\n')
        self.assertFalse(report['loaded_library_identity_valid'])
        self.assertFalse(report['bound_status_valid'])

class LoaderLogRetentionTests(TemporaryTests):
    def test_failed_version_command_retains_both_raw_streams(self):
        stdout,stderr=self.root/'stdout.log',self.root/'stderr.log'
        process=Mock(returncode=2);process.communicate.return_value=('raw stdout\n','raw loader stderr\n')
        with patch.object(prepare.subprocess,'Popen',return_value=process):
            with self.assertRaises(BindingError):
                prepare.bounded(['mock','--version'],env={},cwd=self.root,stdout_path=stdout,stderr_path=stderr)
        self.assertEqual(stdout.read_text(),'raw stdout\n');self.assertEqual(stderr.read_text(),'raw loader stderr\n')

    def test_timed_out_version_command_retains_reaped_streams(self):
        stdout,stderr=self.root/'stdout.log',self.root/'stderr.log'
        process=Mock(pid=123);process.communicate.side_effect=[subprocess.TimeoutExpired(['mock'],1),('partial stdout','partial loader')]
        with patch.object(prepare.subprocess,'Popen',return_value=process),patch.object(prepare.os,'killpg') as kill:
            with self.assertRaises(subprocess.TimeoutExpired):
                prepare.bounded(['mock'],env={},cwd=self.root,timeout=1,stdout_path=stdout,stderr_path=stderr)
        self.assertEqual(stdout.read_text(),'partial stdout');self.assertEqual(stderr.read_text(),'partial loader')
        kill.assert_called_once()
