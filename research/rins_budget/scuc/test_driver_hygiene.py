"""Solver-free checks for publication-time evidence/certificate guards."""
import pathlib
import tempfile
import unittest

from screen_and_solve import dropped_matrix_coefficients, prepare_output_directory


class DriverHygiene(unittest.TestCase):
    def test_refuses_existing_output_and_preserves_evidence(self):
        with tempfile.TemporaryDirectory() as root:
            out=prepare_output_directory(pathlib.Path(root)/'fresh')
            evidence=out/'round_01.sol'
            evidence.write_text('previous evidence')
            with self.assertRaises(FileExistsError):
                prepare_output_directory(out)
            self.assertEqual(evidence.read_text(),'previous evidence')

    def test_dropped_matrix_warning_is_rejected(self):
        log='WARNING: LP matrix packed vector contains 33840 |value| in [2.72764e-20, 9.57312e-15] less than or equal to 1e-09: ignored\n'
        self.assertTrue(dropped_matrix_coefficients(log))

    def test_regular_log_is_not_rejected(self):
        self.assertFalse(dropped_matrix_coefficients('Solving report\n  Status Optimal\n'))


if __name__=='__main__':unittest.main()
