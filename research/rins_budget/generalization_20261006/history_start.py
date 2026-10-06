"""CPU historical commitment proposals. No solver call, bound, or feasibility claim.

Input JSON: query {start, feature, columns, topology}, history list additionally
containing {id, end, label_available, u, checked}. Times are ISO UTC. Features
must share a frozen ordering/scaling established using past training data only.
This low-level interface never reads target solutions. Use the native sparse
start adapter to offer suggestions to an unrestricted full problem.
"""
import argparse, datetime as dt, hashlib, json, math, time
from pathlib import Path


def utc(s):
 t=dt.datetime.fromisoformat(s.replace('Z','+00:00'))
 if t.tzinfo is None: raise ValueError('Timezone required')
 return t.astimezone(dt.timezone.utc)


def propose(query,history,method='consensus',k=3):
 started=time.perf_counter()
 if method not in ('previous','nearest','consensus'): raise ValueError('Unknown method')
 if type(k) is not int or k<1: raise ValueError('k must be a positive integer')
 feature=query['feature']; columns=query['columns']; cutoff=utc(query['start'])
 if not columns or len(set(columns))!=len(columns): raise ValueError('Duplicate/empty columns')
 if not feature or not all(type(v) in (int,float) and math.isfinite(v) for v in feature): raise ValueError('Invalid features')
 eligible=[]; excluded=[]
 ids=[x['id'] for x in history]
 if len(ids)!=len(set(ids)): raise ValueError('Duplicate historical IDs')
 for item in history:
  # Completion of the full 36h window and label availability both precede query.
  if utc(item['end'])>cutoff or utc(item['label_available'])>cutoff:
   excluded.append(dict(id=item['id'],reason='future_or_overlapping_label')); continue
  if item['checked'] is not True or item['topology']!=query['topology'] or item['columns']!=columns:
   excluded.append(dict(id=item['id'],reason='unchecked_or_incompatible')); continue
  f=item['feature']; u=item['u']
  if len(f)!=len(feature) or not all(type(v) in (int,float) and math.isfinite(v) for v in f): raise ValueError('Historical feature mismatch')
  if len(u)!=len(columns) or not all(type(v) is int and v in (0,1) for v in u): raise ValueError('Labels must be literal binary values')
  distance=math.sqrt(sum((x-y)**2 for x,y in zip(f,feature))/len(feature))
  eligible.append((distance,item))
 if method=='previous': eligible.sort(key=lambda pair:(utc(pair[1]['end']),pair[1]['id']),reverse=True)
 else: eligible.sort(key=lambda pair:(pair[0],pair[1]['id']))
 chosen=eligible[:k if method=='consensus' else 1]
 suggestions={}; confidence={}
 if chosen:
  for j,name in enumerate(columns):
   ones=sum(item['u'][j] for _,item in chosen); p=ones/len(chosen)
   confidence[name]=max(p,1-p)
   # Unanimity is a fixed conservative rule, not calibrated probability.
   if method!='consensus' or (len(chosen)>=k and ones in (0,len(chosen))): suggestions[name]=int(p>=0.5)
 return dict(method=method,k=k,neighbors=[dict(id=x['id'],distance=d) for d,x in chosen],excluded=excluded,suggestions=suggestions,vote_fraction=confidence,prediction_seconds=time.perf_counter()-started,full_problem_required=True,hard_fixings_applied=False,feasibility_certified=False,lower_bound=None)


def main():
 p=argparse.ArgumentParser();p.add_argument('input',type=Path);p.add_argument('output',type=Path);p.add_argument('--method',choices=['previous','nearest','consensus'],default='consensus');p.add_argument('--k',type=int,default=3);a=p.parse_args()
 raw=a.input.read_bytes();data=json.loads(raw);result=propose(data['query'],data['history'],a.method,a.k);result['input_sha256']=hashlib.sha256(raw).hexdigest()
 with a.output.open('x') as f: json.dump(result,f,indent=2);f.write('\n')
if __name__=='__main__':main()
