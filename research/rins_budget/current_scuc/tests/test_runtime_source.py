"""Source-only runtime checks: no CDLL, subprocess, model or solver execution."""
import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from current_scuc import runtime


class RuntimeSourceTests(unittest.TestCase):
    def test_duplicate_and_nonfinite_manifest_values_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'record.json'
            for contents in ('{"x":1,"x":2}','{"x":NaN}','{"x":Infinity}'):
                path.write_text(contents)
                with self.assertRaises(ValueError):
                    runtime.strict_json(path)

    def test_git_tree_preserves_names_modes_and_nested_paths(self):
        data=b'hello\n'
        blob=hashlib.sha1(b'blob 6\0'+data).hexdigest()
        row=dict(path='hello.txt',mode='100644',git_blob=blob,sha256=hashlib.sha256(data).hexdigest(),bytes=6)
        # This is the native Git tree serialization, independently assembled.
        payload=b'100644 hello.txt\0'+bytes.fromhex(blob)
        expected=hashlib.sha1(b'tree '+str(len(payload)).encode()+b'\0'+payload).hexdigest()
        self.assertEqual(runtime.git_tree_from_inventory([row]),expected)
        self.assertNotEqual(runtime.git_tree_from_inventory([dict(row,mode='100755')]),expected)
        self.assertNotEqual(runtime.git_tree_from_inventory([dict(row,path='sub/hello.txt')]),expected)
        for bad in ('../hello.txt','/hello.txt','sub/../hello.txt'):
            with self.assertRaises(ValueError):
                runtime.git_tree_from_inventory([dict(row,path=bad)])
        with self.assertRaises(ValueError):
            runtime.git_tree_from_inventory([row,row])

    def test_conditional_debug_and_integer_build_guard(self):
        with tempfile.TemporaryDirectory() as directory:
            cache=Path(directory)/'CMakeCache.txt'; header=Path(directory)/'HConfig.h'
            flags=dict(runtime.EXPECTED_OPTIONS,CMAKE_C_COMPILER='gcc',CMAKE_CXX_COMPILER='g++',CMAKE_GENERATOR='Ninja')
            cache.write_text(''.join(k+':STRING='+v+'\n' for k,v in flags.items()))
            good=('\n'.join('#define '+v for v in ('FAST_BUILD','ZLIB_FOUND','CUPDLP_CPU','HIGHS_SHARED_EXTRAS_LIBRARY'))+
                  '\n#define HIGHS_GITHASH "d547a3ad8a"\n#define HIGHS_VERSION_MAJOR 1\n#define HIGHS_VERSION_MINOR 15\n'
                  '#define HIGHS_VERSION_PATCH 1\n#define CMAKE_BUILD_TYPE "Release"\n')
            header.write_text(good)
            self.assertEqual(runtime.validate_build(cache,header)['DEBUGSOL'],'OFF')
            for macro in ('HIGHSINT64','HIPO','CUPDLP_GPU','HIGHS_DEBUGSOL'):
                header.write_text(good+'#define '+macro+'\n')
                with self.assertRaises(ValueError):
                    runtime.validate_build(cache,header)
            header.write_text(good)
            cache.write_text(cache.read_text().replace('DEBUGSOL:STRING=OFF','DEBUGSOL:STRING=ON'))
            with self.assertRaises(ValueError):
                runtime.validate_build(cache,header)

    def test_guard_inventory_contains_actual_source_consumers(self):
        guards=runtime.source_guard_hashes()
        self.assertEqual(len(guards),16)
        for name in ('highs/Highs.h','highs/interfaces/highs_c_api.h','highs/lp_data/HighsOptions.h',
                     'highs/lp_data/HighsSolve.cpp','highs/lp_data/HighsLpUtils.cpp','highs/io/HighsIO.cpp','app/RunHighs.cpp'):
            self.assertRegex(guards[name],r'^[0-9a-f]{64}$')


@unittest.skipUnless(os.environ.get('CURRENT_SCUC_TEST_RUNTIME_MANIFEST'),'No source-only runtime fixture selected')
class BoundRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path=Path(os.environ['CURRENT_SCUC_TEST_RUNTIME_MANIFEST']).resolve()
        cls.data=runtime.strict_json(cls.path)
        cls.binary=runtime._resolve(cls.path.parent,cls.data['artifacts']['binary']['path'],'binary')

    def normalized_manifest(self):
        data=copy.deepcopy(self.data)
        for key in ('source_root','build_root'):
            data[key]=str(runtime._resolve(self.path.parent,data[key],key))
        for key,row in data['artifacts'].items():
            row['path']=str(runtime._resolve(self.path.parent,row['path'],key))
        return data

    def test_discovery_and_local_config_are_source_only(self):
        found=runtime.discover_runtime(self.binary,self.path)
        cfg=found.driver_config()
        self.assertFalse(cfg['native_qualified'])
        self.assertEqual(cfg['library_sha256'],runtime.sha256(found.library))
        self.assertEqual(runtime.runtime_path('pristine-source/highs/Highs.h',cfg),found.source_root/'highs/Highs.h')
        self.assertEqual(runtime.runtime_path('projected-start-containment-build-v1/native_assess',cfg),found.native_assess)
        self.assertEqual(runtime.discover_runtime(self.binary).manifest_sha256,found.manifest_sha256)

    def test_foreign_commit_byte_tampering_and_missing_evidence_rejected(self):
        changes=[lambda d:d['source'].update(commit='0'*40),
                 lambda d:d['source'].update(tree='0'*40),
                 lambda d:d['artifacts']['library'].update(sha256='0'*64),
                 lambda d:d['artifacts'].pop('native_assess'),
                 lambda d:d['build_options'].update(DEBUGSOL='ON'),
                 lambda d:d['source']['files'][0].update(mode='100755' if d['source']['files'][0]['mode']=='100644' else '100644')]
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'runtime-manifest.json'
            for change in changes:
                data=self.normalized_manifest();change(data);path.write_text(json.dumps(data))
                with self.assertRaises(ValueError):
                    runtime.discover_runtime(self.binary,path)


if __name__=='__main__':
    unittest.main()
