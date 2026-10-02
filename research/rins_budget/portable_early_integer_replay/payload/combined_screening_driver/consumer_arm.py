"""One complete arm owned by the parent process envelope."""
import argparse
from common import *

def main():
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);p.add_argument('--source',required=True)
    p.add_argument('--hours',type=int,required=True);p.add_argument('--seed',type=int,required=True)
    p.add_argument('--arm',choices=['A','early_candidate'],required=True);p.add_argument('--tiny',action='store_true');a=p.parse_args()
    limit();runtime_manifest();plan=read_json(HERE/'CAMPAIGN_PLAN.json');entry=plan['allowed_sources'].get(a.source)
    if entry is None or entry['hours']!=a.hours or (entry['kind']=='synthetic')!=a.tiny:raise ContractError('Unsupported source/tiny binding')
    if (a.tiny and a.seed!=0) or (not a.tiny and a.seed not in (211,212,213)):raise ContractError('Unsupported seed')
    from consumer_runtime import run_arm
    result=run_arm(a.out,Path(a.source),a.hours,a.seed,a.arm,tiny=a.tiny)
    if result.get('stop_campaign'):raise ContractError(result['reason'])

if __name__=='__main__':main()
