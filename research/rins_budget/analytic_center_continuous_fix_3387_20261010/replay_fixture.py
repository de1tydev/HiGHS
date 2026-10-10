import ctypes as C, hashlib, json, pathlib, sys
import argparse
parser=argparse.ArgumentParser(description="Replay the immutable issue3387 MPS against an explicitly pinned local HiGHS DSO")
parser.add_argument('--library',required=True)
parser.add_argument('--sha256',required=True)
parser.add_argument('--model',required=True)
parser.add_argument('--presolve',choices=['off','on'],required=True)
parser.add_argument('--expected-objective',type=float,required=True)
args=parser.parse_args()
lib=pathlib.Path(args.library).resolve()
expected=args.sha256
assert hashlib.sha256(lib.read_bytes()).hexdigest()==expected
presolve=args.presolve
d=C.CDLL(str(lib))
def bind(n,r,args):
 f=getattr(d,'Highs_'+n); f.restype=r; f.argtypes=args; return f
P=C.c_void_p; I=C.c_int; S=C.c_char_p; D=C.c_double
h=bind('create',P,[])()
opts={'presolve':presolve,'threads':1,'random_seed':0,'time_limit':10.0,'log_dev_level':1,'highs_analysis_level':128}
for k,v in opts.items():
 typ='String' if isinstance(v,str) else 'Double' if isinstance(v,float) else 'Int'
 ct=S if typ=='String' else D if typ=='Double' else I
 assert bind('set'+typ+'OptionValue',I,[P,S,ct])(h,k.encode(),v.encode() if isinstance(v,str) else v)==0
assert bind('readModel',I,[P,S])(h,str(pathlib.Path(args.model).resolve()).encode())==0
rc=bind('run',I,[P])(h)
status=bind('getModelStatus',I,[P])(h)
obj=bind('getObjectiveValue',D,[P])(h)
n=bind('getNumCol',I,[P])(h); vals=(D*n)()
assert bind('getSolution',I,[P,C.POINTER(D),C.POINTER(D),C.POINTER(D),C.POINTER(D)])(h,vals,None,None,None)==0
maps=[l for l in pathlib.Path('/proc/self/maps').read_text().splitlines() if 'libhighs' in l]
result={'presolve':presolve,'options':opts,'dso_sha256':expected,'loaded_maps':maps,'run_status':rc,'model_status':status,'objective':obj,'solution':list(vals),'expected_objective':args.expected_objective,'objective_correct':rc==0 and status==7 and obj==args.expected_objective}
assert any(str(lib) in line for line in maps)
assert result['objective_correct'], result
print('RESULT_JSON '+json.dumps(result),flush=True)
bind('destroy',None,[P])(h)
