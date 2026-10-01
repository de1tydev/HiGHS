"""Extract last COMPLETE dense original-column block, ignoring a truncated tail."""
import argparse,json,math,pathlib

def extract(path,expected):
 lines=pathlib.Path(path).read_text().splitlines();complete=[];i=0;objective=None;bad=0
 while i<len(lines):
  if lines[i].startswith('Objective '):
   try:objective=float(lines[i].split()[1])
   except ValueError:objective=None
  if lines[i].startswith('# Columns '):
   n=int(lines[i].split()[2]);values={};start=i+1
   if n!=expected or n<0:raise ValueError('Checkpoint column count does not match original model')
   for line in lines[start:start+n]:
    fields=line.split()
    if len(fields)!=2 or fields[0] in values:break
    try:v=float(fields[1])
    except ValueError:break
    if not math.isfinite(v):break
    values[fields[0]]=v
   if len(values)==expected and objective is not None and math.isfinite(objective):complete.append((objective,values));i=start+n-1
   else:bad+=1
  i+=1
 if not complete:raise ValueError('No complete improving-incumbent checkpoint')
 return complete[-1][1],dict(complete_blocks=len(complete),partial_or_invalid_blocks=bad,last_logged_objective=complete[-1][0],columns=expected)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('checkpoint');p.add_argument('--columns',type=int,required=True);p.add_argument('--output',required=True);a=p.parse_args();x,meta=extract(a.checkpoint,a.columns);pathlib.Path(a.output).write_text(json.dumps(x,separators=(',',':'))+'\n');print(json.dumps(meta,indent=2))
