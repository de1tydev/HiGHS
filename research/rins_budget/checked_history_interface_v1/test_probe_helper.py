"""Deterministic failure fixtures used only by run_functional.py, never driver CLI."""
import json
import os
from pathlib import Path
import sys
import time


def main():
    mode, point, metadata, library, seconds = sys.argv[1:]
    if mode == 'timeout':
        time.sleep(60.)  # Owner must terminate/reap this process at its five-second stage cap.
        raise RuntimeError('Test watchdog did not terminate helper')
    if mode != 'invalid':
        raise ValueError('Unknown test fixture')
    with Path(point).open('x') as stream:
        stream.write('u0 0\n')  # Deliberately incomplete; independent point checker must reject.
    value = dict(schema_version=1, mode='probe', process_id=os.getpid(), outcome='point', error='',
                 loaded_library_path=library, run_api_status=0, native_model_status=7,
                 native_model_status_name='Optimal', complete_primal_present=True, model_fields_verified=True,
                 num_col=4, num_row=3, num_nz=6, point_objective=0., solver_reported_objective=0., options_verified=True,
                 options=dict(threads=2, parallel='off', random_seed=1, time_limit=float(seconds), mip_rel_gap=0, mip_abs_gap=0))
    with Path(metadata).open('x') as stream:
        json.dump(value, stream, allow_nan=False)


if __name__ == '__main__':
    main()
