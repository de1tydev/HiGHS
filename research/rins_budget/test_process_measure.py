import os,sys,tempfile,unittest
from unittest import mock
import process_measure as measure

class ChildResources(unittest.TestCase):
    def run_child(self, code, timeout=3):
        with tempfile.TemporaryFile(mode='w+') as stream:
            return measure.run_measured([sys.executable,'-c',code],stream=stream,env=os.environ,timeout=timeout)
    def test_child_specific_peak(self):
        first=self.run_child('x=bytearray(32*1024*1024)')
        second=self.run_child('pass')
        self.assertEqual(first['solver_returncode'],0)
        self.assertEqual(second['solver_returncode'],0)
        self.assertLess(second['solver_peak_rss_KiB'],first['solver_peak_rss_KiB'])
    def test_watchdog(self):
        result=self.run_child('import time;time.sleep(10)',timeout=.1)
        self.assertTrue(result['hard_watchdog_killed'])
        self.assertEqual(result['solver_returncode'],-9)
    def test_exception_reaps(self):
        original=os.wait4;seen=[]
        def interrupted(pid,flags):
            if not seen:
                seen.append(pid)
                raise KeyboardInterrupt('synthetic cancellation')
            return original(pid,flags)
        with mock.patch.object(measure.os,'wait4',interrupted):
            with self.assertRaises(KeyboardInterrupt):self.run_child('import time;time.sleep(10)')
        with self.assertRaises(ChildProcessError):original(seen[0],os.WNOHANG)
    def test_nonzero_exit(self):
        result=self.run_child('raise SystemExit(7)')
        self.assertEqual(result['solver_returncode'],7)
        self.assertFalse(result['hard_watchdog_killed'])
if __name__=='__main__':unittest.main()
