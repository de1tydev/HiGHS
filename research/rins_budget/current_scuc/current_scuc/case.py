"""Fresh local orchestration manifests for the projected candidate."""
from __future__ import annotations
import os
from pathlib import Path
import sys
from . import case_binding as cb
from . import binding
from ._paths import source_path


def bind_case(case_path):
    path=Path(case_path).resolve()
    value=cb.load(path,cb.sha(path))
    cb.verify_inputs(value)
    os.environ['HELDOUT_CASE_BINDING']=str(path)
    os.environ['HELDOUT_CASE_BINDING_SHA256']=cb.sha(path)
    cb.verify_runtime(value)
    cfg=binding.config()
    os.environ['CURRENT_SCUC_RUNTIME_MANIFEST']=cfg['runtime_manifest']
    return value


def create_arm_manifest(case_path,source_manifest_path,out_path):
    value=bind_case(case_path)
    source_manifest_path=Path(source_manifest_path).resolve()
    binding.verify_package_source(source_manifest_path,cb.sha(source_manifest_path))
    cfg=binding.config()
    cb.require(cfg['source_manifest']==cb.record(source_manifest_path),'Case and arm source manifests differ')
    snapshot=binding.verify_source_snapshot(cfg['source_snapshot'])
    inputs={role:(value['source'] if role=='source' else value['model'][role]) for role in ('source','expected','mps')}
    inputs.update(generator=cb.record(source_path('primal-cache-replay-v4.1/core/scuc/generate.py')),
        library=cb.record(cfg['library']))
    files=dict(cfg['runtime_pins'])
    files.update(cfg.get('runtime_library_pins',{}));files.update(cfg.get('build_pins',{}))
    files[str(Path(cfg['runtime_manifest']).resolve())]=cfg['runtime_manifest_sha256']
    manifest=dict(schema='current-scuc-arm-manifest/v1',root=str(cb.ROOT),
        case_binding=cb.record(case_path),source_manifest=cb.record(source_manifest_path),
        scope=dict(hours=value['case']['hours'],subset_mapping_pairs=[],
            virtual_security_scope='all_source_listed_nonself_outages',original_binary_count=value['shapes']['binary_count'],
            **{k:value['scope'][k] for k in ('signed_normal_rows','signed_security_rows','unsigned_security_pair_hours')}),
        inputs=inputs,
        payload_files=[dict(path=str(cb.ROOT/relative),sha256=digest) for relative,digest in snapshot['files_sha256'].items()],
        runtime=dict(python_executable=cfg['python'],python_version=list(sys.version_info[:3]),
            environment={k:'1' for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS',
                'PYTHONDONTWRITEBYTECODE','PYTHONNOUSERSITE')},
            files=[dict(path=path,sha256=digest) for path,digest in sorted(files.items())],
            config=value['runtime']['config'],native_runtime_manifest=cb.record(cfg['runtime_manifest'])))
    cb.write(out_path,manifest)
    return Path(out_path).resolve()


def create_source_reference(source_manifest_path,out_path):
    path=Path(source_manifest_path).resolve()
    binding.verify_package_source(path,cb.sha(path))
    value=dict(schema='current-scuc-local-source-reference/v1',source_manifest_sha256=cb.sha(path),
        source_manifest_path=str(path))
    cb.write(out_path,value)
    return Path(out_path).resolve()
