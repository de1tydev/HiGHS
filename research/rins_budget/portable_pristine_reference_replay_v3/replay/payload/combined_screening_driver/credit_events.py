"""Read-only RootChildCredit v1 trace checks, never a feasibility or bound source."""
import math
import re

PREFIX='RootChildCredit v1 '
HEADER=re.compile(r'^RootChildCredit v1 (decision|return|skip): (.*)$')
ROOT_ORIGINS={'root-reduced-cost','root-RENS'}
ORIGINS=ROOT_ORIGINS|{'search-RENS','search-RINS','other'}
RESETS={'none','restart','incumbent','original','upper'}
REASONS={'scope','coordinates','termination','time','band','uncalibrated','credit','exhausted'}
EVENTS=RESETS|{'invalid_elapsed','learn','renew','termination','infeasible'}
CHARGES={'none','debit','invalid_elapsed'}
REQUIRED={
 'decision':set('call mode origin phase depth workers parallel_lock restart original u l o r a raw_gap reason reset valid anchor_original anchor_upper S C_before existing_limit proposed_limit applied_limit would_skip skip launch'.split()),
 'return':set('call origin phase event charge solver_elapsed solver_overshoot parent_run_start parent_run_end parent_run_delta parent_import_end parent_import_delta status termination_status first_hit outer_gap_stopped accepted improved pre_original post_original pre_upper post_upper restart valid S C_after'.split()),
 'skip':set('call origin event solver_elapsed C_after'.split()),
}

def number(fields,key,finite=False):
    try:v=float(fields[key])
    except (KeyError,TypeError,ValueError) as exc:raise ValueError('Missing/malformed credit number '+key) from exc
    if finite and not math.isfinite(v):raise ValueError('Nonfinite credit number '+key)
    return v

def integer(fields,key):
    value=number(fields,key,True)
    if not value.is_integer():raise ValueError('Noninteger credit field '+key)
    return int(value)

def parse_credit_events(text,enforced):
    """Main-only unique call IDs are guaranteed by the frozen source scope guard.

    Raw nonfinite inactive objective/offset/gap values remain literal strings as diagnostics.
    Credited amounts and returned timing must be finite. A trace is never added
    to a global lower bound and nested times are never added to process budgets.
    """
    if type(enforced) is not bool:raise ValueError('Credit mode must be bool')
    calls={};order=[];active=None
    for line in text.splitlines():
        if not line.startswith('RootChildCredit '):continue
        match=HEADER.fullmatch(line)
        if not match:raise ValueError('Unknown/malformed credit event version')
        kind,body=match.groups();fields={}
        for token in body.split():
            if token.count('=')!=1:raise ValueError('Malformed credit token')
            key,value=token.split('=',1)
            if not key or not value or key in fields:raise ValueError('Duplicate/empty credit field')
            fields[key]=value
        if set(fields)!=REQUIRED[kind]:raise ValueError('Incomplete/unrecognized credit event fields')
        string_fields={'mode','origin','phase','reason','reset','event','charge'}
        for key in set(fields)-string_fields:number(fields,key)
        call=integer(fields,'call')
        if call<=0 or fields.get('origin') not in ORIGINS:raise ValueError('Invalid credit call/origin')
        if kind=='decision':
            if call in calls or active is not None or call!=len(calls)+1:raise ValueError('Duplicate, out-of-order or overlapping main credit call')
            if fields.get('mode')!=('enforce' if enforced else 'observe'):raise ValueError('Credit mode differs from options')
            if integer(fields,'depth')!=0 or integer(fields,'workers')!=1 or integer(fields,'parallel_lock')!=0:raise ValueError('Unexpected nested/parallel credit event')
            root=fields['origin'] in ROOT_ORIGINS
            if fields.get('phase')!=('root' if root else 'other' if fields['origin']=='other' else 'search'):raise ValueError('Credit phase/origin mismatch')
            if fields['reason'] not in REASONS or fields['reset'] not in RESETS:raise ValueError('Unknown credit decision reason/reset')
            if integer(fields,'restart')<0:raise ValueError('Negative restart epoch')
            skip=integer(fields,'skip');would_skip=integer(fields,'would_skip');valid=integer(fields,'valid')
            if any(v not in (0,1) for v in (skip,would_skip,valid)):raise ValueError('Invalid credit flag')
            current=number(fields,'C_before',True);initial=number(fields,'S',True)
            if current<0 or initial<0:raise ValueError('Negative credit')
            existing=number(fields,'existing_limit');proposed=number(fields,'proposed_limit');applied=number(fields,'applied_limit')
            if any(math.isnan(v) for v in (existing,proposed,applied)):raise ValueError('NaN child limit')
            cap_applied=not skip and applied<existing
            if not enforced and (skip or applied!=existing):raise ValueError('Observation changed a child limit or skipped')
            if (cap_applied or skip) and (not root or not valid):raise ValueError('Credit applied outside calibrated root scope')
            if cap_applied or skip:
                for key in ('original','u','l','o','r','a','raw_gap','anchor_original','anchor_upper'):number(fields,key,True)
                ratio=number(fields,'raw_gap');target=number(fields,'r')
                if not 0<target<ratio<=2*target:raise ValueError('Cap outside reported near-target band')
            if cap_applied and (not math.isfinite(applied) or applied<=0 or applied>current or applied!=proposed):raise ValueError('Invalid applied credit cap')
            if skip and (not would_skip or current!=0 or applied!=0):raise ValueError('Invalid exhausted-credit skip')
            if enforced and bool(skip)!=bool(would_skip):raise ValueError('Enforced skip differs from proposed skip')
            for key in ('launch',):
                if number(fields,key,True)<0:raise ValueError('Negative event time')
            calls[call]={'decision':fields,'cap_applied':cap_applied,'skipped':bool(skip),'shadow_cap':not would_skip and proposed<existing,'raw_decision':line}
            order.append(call);active=call
        else:
            if call not in calls or active!=call or 'terminal' in calls[call]:raise ValueError('Unmatched/duplicate credit terminal')
            decision=calls[call]['decision']
            if fields['origin']!=decision['origin']:raise ValueError('Terminal caller differs')
            if number(fields,'solver_elapsed',True)<0 or number(fields,'C_after',True)<0:raise ValueError('Invalid returned credit timing')
            if kind=='skip':
                if not calls[call]['skipped'] or fields.get('event')!='skip' or number(fields,'solver_elapsed')!=0:raise ValueError('Unplanned skip terminal')
            else:
                if calls[call]['skipped'] or fields.get('phase')!=decision['phase']:raise ValueError('Return scope mismatch')
                if fields['event'] not in EVENTS or fields['charge'] not in CHARGES:raise ValueError('Unknown credit return event/charge')
                if integer(fields,'restart')<0:raise ValueError('Negative restart epoch')
                for key in ('status','termination_status'):
                    if not 0<=integer(fields,key)<=19:raise ValueError('Unknown solver status')
                for key in ('valid','outer_gap_stopped'):
                    if integer(fields,key) not in (0,1):raise ValueError('Invalid returned boolean flag')
                for key in ('parent_run_start','parent_run_end','parent_run_delta','parent_import_end','parent_import_delta','S'):
                    if number(fields,key,True)<0:raise ValueError('Negative returned parent time or credit')
                if number(fields,'first_hit',True)<-1:raise ValueError('Invalid first-hit time')
                accepted=integer(fields,'accepted');improved=integer(fields,'improved')
                if accepted not in (0,1) or improved not in (0,1) or improved>accepted:raise ValueError('Invalid incumbent flags')
                if number(fields,'solver_overshoot',True)<0:raise ValueError('Negative local overshoot')
                if fields.get('event') in {'learn','renew'}:
                    if not accepted or not improved or integer(fields,'valid')!=1 or number(fields,'solver_elapsed',True)<=0 or number(fields,'S',True)!=number(fields,'solver_elapsed',True) or number(fields,'C_after')!=number(fields,'S'):raise ValueError('Invalid credit renewal')
            calls[call]['terminal']={'kind':kind,'fields':fields,'raw':line};active=None
    if active is not None:raise ValueError('Incomplete main credit call')
    ordered=[calls[c] for c in order]
    return {'version':1,'mode':'enforce' if enforced else 'observe','call_count':len(ordered),'calls':ordered,
            'applied_caps':sum(c['cap_applied'] for c in ordered),'applied_skips':sum(c['skipped'] for c in ordered),
            'root_origins_observed':sorted({c['decision']['origin'] for c in ordered if c['decision']['origin'] in ROOT_ORIGINS}),
            'global_bound_eligible':False,'nested_time_added_to_process_budget':False}
