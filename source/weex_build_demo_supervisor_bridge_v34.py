from pathlib import Path
R=Path(__file__).resolve().parent
src=(R/'weex_demo_crash_recovery_20261109.py').read_text(encoding='utf-8')
new=src
def change(old, replacement):
 global new
 if new.count(old)!=1:raise RuntimeError('SOURCE_MISMATCH '+old[:60]+' count '+str(new.count(old)))
 new=new.replace(old,replacement,1)
change("OUT=R/'weex_demo_crash_recovery_20261109_result.json'","OUT=R/'weex_demo_supervisor_bridge_v34_result.json'")
change("CHILD=R/'weex_demo_crash_child_20261109.py'","CHILD=R/'weex_demo_supervisor_crash_child_v34.py'")
change("CLIENT='wxpilot_crashsim_20261109a01'","CLIENT='wxpilot_crashsim_v34a01'")
change("FILE=R/'weex_demo_crash_child_state_20261109.json'","FILE=R/'weex_demo_supervisor_child_v34_state.json'")
change("statefile=R/'weex_demo_crash_child_state_20261109.json'","statefile=R/'weex_demo_supervisor_child_v34_state.json'")
start="        close={'symbol':'ETHUSDT','positionId':int(p[0]['id'])}"
end="        save(report);return report"
i=new.index(start);j=new.index(end,i)+len(end)
replacement='''        # Route the exact SIM close through the production supervisor tick,
        # with strictly DEMO-only adapters and its own temporary state root.
        # Never authorize or import an EXIT permit on production.
        from tempfile import TemporaryDirectory
        from weex_supervised_process_monitor_v6 import tick
        close={'symbol':'ETHUSDT','positionId':int(p[0]['id'])}
        def sim_worker_recovery(_):
            if not (proc.returncode==73 and report['noDuplicateEntry'] and report['stopVerified']):
                return {'status':'DEMO_WORKER_READBACK_UNVERIFIED','workerRestartConfirmed':False}
            # A demo child is not the real production worker; report the truth.
            return {'status':'DEMO_READBACK_PASS_NOT_PRODUCTION_WORKER','workerRestartConfirmed':False}
        def sim_exit_executor(_):
            session.closebody=close
            report.update(status='CLOSE_OUTCOME_UNKNOWN',demoClosePOSTs=1)
            save(report)
            ack=c.rest_api.execute_operation('post_capi_v3_closePositions',{'body':close}).data
            report['closeAcknowledged']=(isinstance(ack,list) and len(ack)==1 and
                ack[0].get('success') is True and str(ack[0].get('positionId'))==str(close['positionId']))
            report['closeOrderId']=str(ack[0].get('successOrderId')) if report['closeAcknowledged'] else None
            positions=read('get_capi_v3_account_position_allPosition')
            orders=read('get_capi_v3_openOrders')
            algos=read('get_capi_v3_openAlgoOrders')
            report['accountFlat']=positions==orders==algos==[]
            report['remaining']={'positions':len(positions),'orders':len(orders),'algos':len(algos)}
            passed=all((report['exactEntryVerified'],report['stopVerified'],
                       report['noDuplicateEntry'],report['closeAcknowledged'],report['accountFlat']))
            report['status']='DEMO_SUPERVISOR_TICK_EXIT_PASS' if passed else 'DEMO_REQUIRES_REVIEW'
            save(report)
            return {'status':'CLOSE_VERIFIED_BY_INDEPENDENT_GET' if passed else 'CLOSE_READBACK_UNCERTAIN',
                    'verifiedFlat':bool(passed),'releaseCertified':False}
        with TemporaryDirectory(prefix='weex_sim_supervisor_v34_') as td:
            proof=tick(td,
              observer=lambda _:{'status':'VERIFIED_PROTECTED_REQUIRES_EXTERNAL_CLOSE_APPROVAL'},
              recovery_planner=lambda _:{'status':'EXACT_CLOSE_PROPOSAL_REQUIRES_SEPARATE_AUTHORIZATION'},
              worker_recovery=sim_worker_recovery,
              exit_policy_reader=lambda _:{'canClose':True,'scope':'SIM_ONLY_V34'},
              exit_executor=sim_exit_executor)
        report['monitorProof']={
            'monitorStatus':proof['status'],'incident':proof['incident'],
            'recoveryProposalStatus':proof['recoveryProposalStatus'],
            'workerRestartResult':proof['workerRestartResult'],
            'workerRestartConfirmed':proof['workerRestartConfirmed'],
            'exitPolicyResult':proof['exitPolicyResult'],
            'possibleReduceOnlyClosePosts':proof['possibleReduceOnlyClosePosts'],
            'entryDispatchAllowed':proof['entryDispatchAllowed'],
            'releaseCertified':proof['releaseCertified'],
            'demoPermissionOnly':True}
        if report.get('status')!='DEMO_SUPERVISOR_TICK_EXIT_PASS':
            report['status']='DEMO_SUPERVISOR_TICK_UNVERIFIED'
        save(report);return report'''
new=new[:i]+replacement+new[j:]
# One-shot artifact namespace and host checks are preserved.
compile(new,str(R/'weex_demo_supervisor_bridge_v34.py'),'exec')
out=R/'weex_demo_supervisor_bridge_v34.py'
if out.exists():raise RuntimeError('V34_ALREADY_EXISTS')
out.write_text(new,encoding='utf-8')
print('BUILT',str(out),'ONLY_DEMO_HOST',new.count("HOST='https://api-sim.weex.com'")==1)
