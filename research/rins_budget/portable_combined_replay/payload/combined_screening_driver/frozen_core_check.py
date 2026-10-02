#!/usr/bin/env python3
"""Direct historical-core check of one tiny witness, with portable bindings only."""
import argparse
import sys
from contracts import *

# Exact public source identities; model-stage documentation is curated.
# Historical/core AST equivalence is recorded in SOURCE_IDENTITIES.json. No selector is used.
FROZEN_CORE = {'model_stage.py': 'b2dc7e0f02a66c492c33bcf2448bb0f0ebf40951ebf17a470130166bf7ac0e62', 'primal_and_bound.py': '2409b1b25a39f69e2bfda624656181027ff7413c9bc1a58eb6da300800d9bd00', 'fractional_separator.py': '0760ccabff276b927cc746437e8ee83c0517e00c6aa27f0bf12de043a50582bb', '../scuc/generate.py': 'ea57607bc600ee425c3a465dbda9ecf3980d98b06c4f305520ea2b0dc90c7e04', '../scuc/check_solution.py': '77ccd22d490282709bb66f38566b571518cf8f2e5bc4478dcd3a548fcb7af024', '../canonical_mps_export/export_v2.py': 'dab515d7a9a4657358df9ed842a239a7b5a327319ae76bdf19801c09389fec5d', '../canonical_mps_export/readback.py': '4400ec93e891719348dc3c574c4a5f4e1b3b2c26b00825ae4ecef3c977d52755'}

def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('pairs','kind','model','solution','result','receipt'): p.add_argument('--'+name, required=True)
    args = p.parse_args()
    if args.kind not in ('lp','mip'): raise ContractError('Unknown tiny witness kind')
    runtime_manifest()
    core = {str((HERE/name).resolve()):digest for name,digest in FROZEN_CORE.items()}
    verify(core)
    # Fresh interpreter, default baseline separator and unchanged measured core.
    # This deliberately bypasses stage_child/load_selected and their plan dispatch.
    import model_stage
    result = model_stage.check(HERE/'tiny_triangle.json',2,args.pairs,args.kind,args.model,args.solution)
    verify(core); runtime_manifest()
    write_json(args.result,result,fresh=True)
    write_json(args.receipt,{'passed':True,'core_sha256':core,'runtime_manifest_sha256':sha(HERE/'REVIEW_MANIFEST.json'),
        'result_sha256':sha(args.result),'python_executable':sys.executable,
        'dispatch':'direct unchanged historical core; portable path/runtime binding; baseline separator',
        'excluded_result_fields':[]},fresh=True)

if __name__ == '__main__': main()
