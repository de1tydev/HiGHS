"""Small stage adapter; all source, matrix, outage, row and selector gates inherited."""
import re
import sys
import time
from common import *
import cold_screen_pair as existing
from trial_policy import DISCOVERY, PROOF, options_text, validate_options, report_for_role, run_pipeline

class Backend(existing.RuntimeBackend):
    def __init__(self, out, source, hours, *, tiny, candidate):
        super().__init__(out,source,hours,0,tiny=tiny,arm='A')
        self.candidate=candidate
        self.env=environment()

    def start(self,state):
        verify_trial(); health()
        super().start(state)
        state.update(arm='early_candidate' if self.candidate else 'A', common_pipeline_arm='A',
                     common_options=existing.options_text('mip',False), trial_manifest_sha256=sha(HERE/'RUNTIME_MANIFEST.json'))
        for role in (PROOF,DISCOVERY):
            path=self.out/(role+'.options');path.write_text(options_text(role))
            self.tracked[str(path)]=sha(path)
        self.checkpoint(state)

    def stage(self,role,active,allocation,debit,rec):
        stage_started=time.monotonic()
        verify_trial();verify(self.tracked);health();self.stages+=1
        options=self.out/(role+'.options');validate_options(role,options.read_text())
        rd=self.out/f'{self.stages:02d}_{role}';rd.mkdir(exist_ok=False)
        pair_path=rd/'pairs.json';model=rd/'master.mps';solution=rd/'solution.sol'
        write_json(pair_path,self.pair_manifest(active),fresh=True)
        rec.update(stage_directory=str(rd),pairs_sha256=sha(pair_path))
        meta=self.auxiliary('generate','mip',rd,model,pair_path,solution,rec)
        rec['model_metadata']=meta
        local=dict(self.tracked,**{str(p):sha(p) for p in (pair_path,model,Path(str(model)+'.expected.json'),
                 Path(str(model)+'.readback.json'),Path(str(model)+'.meta.json'),Path(str(model)+'.readback.log'))})
        verify(local)
        command=[str(BINARY),str(model),'--options_file',str(options),'--time_limit',format(allocation,'.17g'),
                 '--random_seed',str(self.seed),'--solution_file',str(solution)]
        rec.update(solver_command=command,solver_watchdog_seconds=allocation+self.mip_grace,
                   no_incumbent_basis_or_state_input=True)
        before=rd/'record.before_solve.json';write_json(before,rec,fresh=True)
        measured=execute(command,rd/'solver.log',rec['solver_watchdog_seconds'],solver=True)
        solver_returned=time.monotonic()
        # Exactly one debit occurs before any parsing, identity check or failure.
        debit(measured);write_json(rd/'measurement.json',measured,fresh=True)
        if (measured.get('returncode')!=0 or measured.get('hard_watchdog_killed') or measured.get('interrupted')
            or measured.get('launch_or_measurement_error')):
            raise ContractError('Failed/killed solver; retained unparsed output')
        verify(local)
        text=(rd/'solver.log').read_text()
        io_filter=module(EXPORTER/'io_announcements.py','portable_exact_io_announcements')
        report_text,rec['io_announcement_filter']=io_filter.filter_known_io(text,model,solution,solver=True)
        report=report_for_role(report_text,measured,model,role)
        # Display/child telemetry is diagnostic, not a second debit or a bound source.
        first=None
        for line in text.splitlines():
            tokens=line.split()
            percent=next((i for i,t in enumerate(tokens) if re.fullmatch(r'[0-9.]+%',t)),None)
            if percent is None or len(tokens)<percent+8 or not re.fullmatch(r'[0-9.]+s',tokens[-1]):continue
            try:value=float(tokens[percent+2]);seconds=float(tokens[-1][:-1])
            except (ValueError,IndexError):continue
            if finite(value):first=dict(line=line,printed_primal=value,logged_seconds=seconds);break
        parent=text.split('Solving report')[-1]
        rec['diagnostics']=dict(first_logged_finite_incumbent=first,
            first_incumbent_scope='Earliest finite progress-table incumbent line; not a guaranteed chronological first solution; printed clock resolution only',
            return_minus_first_logged_seconds_approx=measured['process_wall_seconds']-first['logged_seconds'] if first else None,
            root_timing_lines=[line for line in text.splitlines() if line.startswith('MIP-Timing:')],
            final_work_lines=[line for line in parent.splitlines() if re.match(r'^  (Timing|Nodes|LP iterations|Max sub-MIP depth|Primal bound|Dual bound)',line)])
        from credit_events import parse_credit_events
        rec['root_child_credit']=parse_credit_events(text,False)
        report['master_identity']=dict(role=role,kind='mip',stage_index=self.stages,stage_directory=str(rd),
            model_path=str(model),hours=self.hours,objective_scope=meta['objective_scope'],source_sha256=sha(self.source),
            model_sha256=sha(model),expected_sha256=sha(str(model)+'.expected.json'),pair_manifest_sha256=sha(pair_path),
            api_report_sha256=sha(str(model)+'.readback.json'),options_sha256=sha(options),executable_sha256=sha(BINARY),
            generator_sha256=sha(GENERATOR),checker_sha256=sha(CHECKER),runtime_manifest_sha256=sha(DRIVER/'RUNTIME_MANIFEST.json'),
            trial_manifest_sha256=sha(HERE/'RUNTIME_MANIFEST.json'))
        checked=None
        if solution.exists():
            local[str(solution)]=sha(solution);rec['solution_sha256']=sha(solution)
            # Only clean exact-role final reports reach the unchanged complete checker.
            checked=self.auxiliary('check','mip',rd,model,pair_path,solution,rec)
            checked['check_artifact']={'path':str(rd/'check.json'),'sha256':sha(rd/'check.json')}
            local[str(rd/'check.json')]=sha(rd/'check.json');local[str(rd/'check.log')]=sha(rd/'check.log')
            if checked.get('primal_present') and checked.get('status')!=report['status']:
                raise ContractError('Solution and exact report status disagree')
            if role==DISCOVERY:
                # Original audit remains unchanged on disk; role-scoped receipt is diagnostic only.
                checked=dict(checked,role=role,upper_bound_eligible=False,certificate_bound_eligible=False,
                             checked_upper=None,discovery_source_secure=checked.get('full_source_primal_pass',False))
        verify(local)
        rec['diagnostics'].update(return_to_check_complete_seconds=time.monotonic()-solver_returned,
                                  stage_through_check_seconds=time.monotonic()-stage_started)
        result=dict(report=report,check=checked,solution_presence='file' if solution.exists() else 'missing',
                    record_before_solve_path=str(before),record_sha256_before_solve=sha(before))
        rec.update(result);write_json(rd/'record.json',rec,fresh=True)
        return result
