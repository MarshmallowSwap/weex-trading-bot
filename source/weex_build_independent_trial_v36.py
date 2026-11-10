from pathlib import Path
R=Path(__file__).resolve().parent
src=(R/'weex_demo_supervisor_bridge_v34.py').read_text(encoding='utf-8')
new=src
def one(old,n):
 global new
 if new.count(old)!=1:raise ValueError('MISMATCH: '+old+' count='+str(new.count(old)))
 new=new.replace(old,n,1)
one("OUT=R/'weex_demo_supervisor_bridge_v34_result.json'","OUT=R/'weex_demo_independent_supervisor_v36_result.json'")
one("CHILD=R/'weex_demo_supervisor_crash_child_v34.py'","CHILD=R/'weex_demo_independent_crash_child_v36.py'")
one("CLIENT='wxpilot_crashsim_v34a01'","CLIENT='wxpilot_crashsim_v36a01'")
one("FILE=R/'weex_demo_supervisor_child_v34_state.json'","FILE=R/'weex_demo_independent_child_v36_state.json'")
one("statefile=R/'weex_demo_supervisor_child_v34_state.json'","statefile=R/'weex_demo_independent_child_v36_state.json'")
start="        # Route the exact SIM close through the production supervisor tick,"
end="        save(report);return report"
i=new.index(start)
j=new.index(end,i)+len(end)
repl='''        # The existing parent DOES NOT close. It starts an independent
        # supervisor operating system process, which independently reads
        # exact SIM exposure, invokes recovery v8 and the real worker CLI,
        # and sends one exact SIM close before final account readback.
        from tempfile import TemporaryDirectory
        manifest=R/'weex_demo_independent_supervisor_v36_manifest.json'
        body={'host':HOST,'clientId':CLIENT,'childExitCode':proc.returncode,
              'stage':report['childState'].get('stage'),
              'entryOrderId':report['entryOrderId'],
              'stopPrice':report['childState'].get('stopPrice')}
        with manifest.open('x',encoding='utf-8') as f:
            json.dump(body,f,sort_keys=True)
        report['status']='INDEPENDENT_SUPERVISOR_HANDOFF_RESERVED'
        save(report)
        with TemporaryDirectory(prefix='weex_sim_independent_v36_') as td:
            exe=getattr(sys,'_base_executable',sys.executable)
            worker=R/'weex_sim_independent_supervisor_v36.py'
            runner=subprocess.run([exe,'-B',str(worker),td,str(manifest)],
                         cwd=str(R),capture_output=True,text=True,timeout=45)
            try:supervisor=json.loads(runner.stdout.strip())
            except (ValueError,TypeError):supervisor={'status':'INDEPENDENT_SUPERVISOR_INVALID_OUTPUT'}
            report['supervisor']=supervisor
            report['supervisorExitCode']=runner.returncode
        report['demoClosePOSTs']=supervisor.get('simClosePostsBySupervisor',0)
        close=supervisor.get('close') or {}
        report['closeAcknowledged']=close.get('closeAcknowledged') is True
        report['closeOrderId']=close.get('closeOrderId')
        report['accountFlat']=close.get('flatReadback') is True
        report['remaining']=close.get('remaining')
        report['workerRestartConfirmed']=supervisor.get('workerRestartConfirmed') is True
        report['status']='DEMO_INDEPENDENT_SUPERVISOR_REAL_WORKER_PASS' if (
          runner.returncode==0 and
          supervisor.get('status')=='INDEPENDENT_SIM_SUPERVISOR_RECOVERY_EXIT_PASS' and
          report['workerRestartConfirmed'] and report['closeAcknowledged'] and
          report['accountFlat'] and report['demoClosePOSTs']==1) else 'DEMO_INDEPENDENT_SUPERVISOR_REVIEW_REQUIRED'
        save(report);return report'''
new=new[:i]+repl+new[j:]
compile(new,str(R/'weex_demo_independent_supervisor_trial_v36.py'),'exec')
out=R/'weex_demo_independent_supervisor_trial_v36.py'
if out.exists():raise RuntimeError('V36_ALREADY_EXISTS')
out.write_text(new,encoding='utf-8')
print('V36_BUILT')
