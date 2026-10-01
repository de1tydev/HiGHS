#!/usr/bin/env python3
"""Fetch only manifest-listed public files; reject changed upstream bytes."""
import argparse,hashlib,json,pathlib,urllib.request
ROOT=pathlib.Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('--case',action='append',help='e.g. case89pegase_2017-02-01; repeatable');p.add_argument('--all',action='store_true');a=p.parse_args()
manifest=json.loads((ROOT/'data_manifest.json').read_text())
selected=[]
for e in manifest['instances']:
 stem=pathlib.Path(e['file']).name.removesuffix('.json.gz')
 if a.all or stem in (a.case or ['case89pegase_2017-02-01']):selected.append(e)
if not selected:p.error('No manifest cases selected')
for e in selected:
 dest=ROOT/e['file'];dest.parent.mkdir(parents=True,exist_ok=True)
 data=dest.read_bytes() if dest.exists() else urllib.request.urlopen(e['url'],timeout=60).read()
 actual=hashlib.sha256(data).hexdigest()
 if actual!=e['sha256']:raise SystemExit(f'Hash mismatch for {dest.name}: {actual}; expected {e["sha256"]}. Do not silently replace the benchmark revision.')
 if not dest.exists():dest.write_bytes(data)
 print(dest.name,actual)
