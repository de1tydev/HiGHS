import copy
import unittest
from credit_events import parse_credit_events


def line(kind, values):
    return 'RootChildCredit v1 '+kind+': '+' '.join(f'{k}={v}' for k,v in values.items())


def decision(enforced=True):
    return dict(call=1,mode='enforce' if enforced else 'observe',origin='root-RENS',phase='root',depth=0,
                workers=1,parallel_lock=0,restart=0,original=100,u=90,l=88.5,o=10,r=.01,a=1e-6,
                raw_gap=.015,reason='credit',reset='none',valid=1,anchor_original=100,anchor_upper=90,
                S=2,C_before=2,existing_limit=500,proposed_limit=2,applied_limit=2 if enforced else 500,
                would_skip=0,skip=0,launch=4)


def returned():
    return dict(call=1,origin='root-RENS',phase='root',event='none',charge='debit',solver_elapsed=2.1,
                solver_overshoot=.1,parent_run_start=4,parent_run_end=6.1,parent_run_delta=2.1,
                parent_import_end=6.2,parent_import_delta=.1,status=13,termination_status=0,first_hit=-1,
                outer_gap_stopped=0,accepted=1,improved=0,pre_original=100,post_original=100,
                pre_upper=90,post_upper=90,restart=0,valid=1,S=2,C_after=0)


class TraceTests(unittest.TestCase):
    def test_real_cap_and_actual_overshoot_are_diagnostics_only(self):
        d,r=decision(),returned();x=parse_credit_events(line('decision',d)+'\n'+line('return',r),True)
        self.assertEqual(x['applied_caps'],1);self.assertEqual(x['calls'][0]['terminal']['fields']['solver_elapsed'],'2.1')
        self.assertFalse(x['global_bound_eligible']);self.assertFalse(x['nested_time_added_to_process_budget'])

    def test_observation_keeps_existing_limit_despite_shadow_cap(self):
        x=parse_credit_events(line('decision',decision(False))+'\n'+line('return',returned()),False)
        self.assertEqual(x['applied_caps'],0);self.assertTrue(x['calls'][0]['shadow_cap'])
        bad=decision(False);bad['applied_limit']=2
        with self.assertRaisesRegex(ValueError,'Observation changed'):parse_credit_events(line('decision',bad),False)

    def test_exhausted_skip_and_invalid_skip(self):
        d=decision();d.update(C_before=0,proposed_limit=0,applied_limit=0,would_skip=1,skip=1)
        terminal=dict(call=1,origin='root-RENS',event='skip',solver_elapsed=0,C_after=0)
        x=parse_credit_events(line('decision',d)+'\n'+line('skip',terminal),True);self.assertEqual(x['applied_skips'],1)
        d['C_before']=.1
        with self.assertRaises(ValueError):parse_credit_events(line('decision',d),True)

    def test_wrong_mode_scope_band_or_nonfinite_credit_rejects(self):
        for key,value in [('mode','observe'),('depth',1),('workers',2),('parallel_lock',1),('raw_gap',.1),('C_before','nan'),('valid',0),('origin','search-RINS')]:
            with self.subTest(key=key):
                d=decision();d[key]=value
                with self.assertRaises(ValueError):parse_credit_events(line('decision',d),True)

    def test_no_trace_is_valid_but_not_activation(self):
        x=parse_credit_events('ordinary presolved empty model log',True);self.assertEqual(x['applied_caps'],0);self.assertEqual(x['call_count'],0)

    def test_missing_duplicate_or_incomplete_events_reject(self):
        d=decision();r=returned();dline=line('decision',d);rline=line('return',r)
        for text in [dline,rline,dline+'\n'+dline,dline+'\n'+rline+'\n'+rline,dline+' duplicate=1 duplicate=2',dline.replace(' r=0.01',''),dline.replace(' v1 ',' v2 ')]:
            with self.subTest(text=text):
                with self.assertRaises(ValueError):parse_credit_events(text,True)

    def test_credit_renewal_needs_actual_accepted_improvement(self):
        r=returned();r.update(event='learn',accepted=1,improved=1,S=2.1,C_after=2.1)
        parse_credit_events(line('decision',decision())+'\n'+line('return',r),True)
        for key,value in [('improved',0),('accepted',0),('S',4),('C_after',0)]:
            bad=copy.deepcopy(r);bad[key]=value
            with self.assertRaises(ValueError):parse_credit_events(line('decision',decision())+'\n'+line('return',bad),True)

    def test_inactive_nonfinite_gap_is_preserved_as_text(self):
        d=decision(False);d.update(original='inf',u='inf',l='-inf',raw_gap='nan',valid=0,S=0,C_before=0,proposed_limit=500)
        r=returned();r.update(event='none',charge='none',S=0,C_after=0,accepted=0)
        x=parse_credit_events(line('decision',d)+'\n'+line('return',r),False)
        self.assertEqual(x['calls'][0]['decision']['raw_gap'],'nan')

    def test_unknown_enums_nonfinite_timers_and_invalid_flags_reject(self):
        mutations=[('decision','reason','bogus'),('decision','reset','bogus'),
            ('decision','restart',-1),('decision','restart',.5),
            ('return','event','bogus'),('return','charge','charge'),
            ('return','valid',2),('return','outer_gap_stopped',2),
            ('return','status',20),('return','status',.5),('return','termination_status',-1),
            ('return','restart',-1),('return','restart',.5),('return','first_hit','inf')]
        mutations += [('return',key,v) for key in ('parent_run_start','parent_run_end','parent_run_delta','parent_import_end','parent_import_delta','S') for v in ('nan','inf',-1)]
        for kind,key,value in mutations:
            with self.subTest(kind=kind,key=key,value=value):
                d,r=decision(),returned();(d if kind=='decision' else r)[key]=value
                with self.assertRaises(ValueError):parse_credit_events(line('decision',d)+'\n'+line('return',r),True)

    def test_renew_requires_actual_positive_accepted_improvement(self):
        d,r=decision(),returned();r.update(event='renew',accepted=1,improved=1,S=2.1,C_after=2.1)
        parse_credit_events(line('decision',d)+'\n'+line('return',r),True)
        for key,value in [('improved',0),('accepted',0),('valid',0),('solver_elapsed',0),('S',4),('C_after',0)]:
            bad=copy.deepcopy(r);bad[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):parse_credit_events(line('decision',d)+'\n'+line('return',bad),True)

if __name__=='__main__':unittest.main()
