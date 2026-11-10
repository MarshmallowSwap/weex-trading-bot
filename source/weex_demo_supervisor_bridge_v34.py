"""One-shot controlled OS-crash after REAL WEEX DEMO protected entry POST.
Production remains STOPPED. Demo is ISOLATED 1x, exact one-shot order.
Child dies before persisting ACK; parent reconciles using demo authenticated GETs,
closes only exact observed position and proves account flat. Never retries POST.
"""
import json,os,subprocess,sys,time,requests
from pathlib import Path
from datetime import datetime,timezone
from decimal import Decimal as D
from urllib.parse import urlsplit,parse_qs
import live_control
from weex_http_guard import sdk_types
from weex_pilot_attached_stop_evidence import protected_entry
R=Path(__file__).resolve().parent
OUT=R/'weex_demo_supervisor_bridge_v34_result.json'
CHILD=R/'weex_demo_supervisor_crash_child_v34.py'
CLIENT='wxpilot_crashsim_v34a01'
HOST='https://api-sim.weex.com'
SRC=R/'weex_sim_active_stop_close_trial_20261109_run2.py'
def save(x):
    tmp=OUT.with_suffix('.tmp');tmp.write_text(json.dumps(x,indent=2));os.replace(tmp,OUT)
def main():
    report={'at':datetime.now(timezone.utc).isoformat(),'host':HOST,'clientOrderId':CLIENT,'status':'NOT_STARTED','realOrders':0,'demoEntryPOSTs':0,'demoClosePOSTs':0,'retries':0}
    if OUT.exists():return {'status':'ONE_SHOT_RESERVED','report':str(OUT)}
    if live_control.state(R)['mode']!='STOPPED' or live_control.build_errors(R):return {'status':'PRODUCTION_NOT_STOPPED'}
    creds=json.loads((R/'weex_sim_v3_credentials.json').read_text());assert creds['environment']=='WEEX_SIM_V3'
    cfg,contract,ops=sdk_types()
    # Leverage and account-flat preflight through the existing allowlisted demo transport
    from weex_sim_active_stop_close_trial_20261109_run2 import SimSession
    pre=SimSession(ops)
    c=contract(config_rest_api=cfg(base_path=HOST,api_key=creds['api_key'],api_secret=creds['secret_key'],passphrase=creds['passphrase'],session=pre,timeout=8,max_retries=0))
    def get(n,q=None):return c.rest_api.execute_operation(n,{'query':q or {}}).data
    try:
        p=get('get_capi_v3_account_position_allPosition');o=get('get_capi_v3_openOrders');a=get('get_capi_v3_openAlgoOrders')
        setting=get('get_capi_v3_account_symbolConfig',{'symbol':'ETHUSDT'})
        if not (p==o==a==[] and isinstance(setting,list) and len(setting)==1 and setting[0].get('marginType')=='ISOLATED' and D(str(setting[0].get('isolatedLongLeverage')))==1):
            return {'status':'SIM_NOT_FLAT_OR_NOT_ISOLATED_1X'}
    finally:pre.shutdown()
    # Derive child only from validated existing protected-entry runner; abort if upstream changed.
    src=SRC.read_text(encoding='utf-8')
    old="    ack=c.rest_api.execute_operation('post_capi_v3_order',{'body':payload})"
    # The original line has 4 or 5 spaces after try: verify match exactly
    old="    ack=c.rest_api.execute_operation('post_capi_v3_order',{'body':payload})"
    if src.count(old)!=1 or src.count("CLIENT='wxpilot_sim_eth_20261109_run2'")!=1:raise ValueError('RUNNER_TEMPLATE_CHANGED')
    code=src.replace("CLIENT='wxpilot_sim_eth_20261109_run2'",f"CLIENT='{CLIENT}'")
    code=code.replace("FILE=R/'weex_sim_active_stop_close_trial_20261109_run2.json'","FILE=R/'weex_demo_supervisor_child_v34_state.json'")
    code=code.replace(old,old+'\n    os._exit(73)',1)
    CHILD.write_text(code,encoding='utf-8');compile(code,str(CHILD),'exec')
    report.update(status='CHILD_DISPATCH_RESERVED',demoEntryPOSTs=1)
    save(report)
    # Crash must occur AFTER successful DEMO POST response, before acknowledgement is persisted
    proc=subprocess.run([sys.executable,'-B',str(CHILD)],cwd=R,capture_output=True,text=True,timeout=35)
    report['childExitCode']=proc.returncode
    statefile=R/'weex_demo_supervisor_child_v34_state.json'
    report['childState']=json.loads(statefile.read_text()) if statefile.exists() else None
    save(report)
    # Parent can never submit another entry. Only observed positionId may be closed.
    class ReadClose:
        def __init__(self):
            self.s=requests.Session();self.closed=False
            self.readpaths={ops[n]['path'] for n in ('get_capi_v3_account_position_allPosition','get_capi_v3_openOrders','get_capi_v3_openAlgoOrders','get_capi_v3_order_history','get_capi_v3_order','get_capi_v3_userTrades')}
            self.closebody=None
        def request(self,method,url,**kw):
            u=urlsplit(url);q=parse_qs(u.query)
            if u.scheme!='https' or u.netloc!='api-sim.weex.com' or u.fragment or kw.get('json') is not None:raise PermissionError('DEMO_HOST_ONLY')
            if method=='GET':
                if u.path not in self.readpaths or kw.get('data') not in (None,'',b'') or (q and not (q=={'symbol':['ETHUSDT']} or u.path=='/capi/v3/order' and set(q)=={'orderId'})):
                    raise PermissionError('DEMO_GET_NOT_ALLOWED')
            elif method=='POST':
                if u.path!='/capi/v3/closePositions' or self.closed or self.closebody is None or json.loads(kw.get('data') or '{}')!=self.closebody:raise PermissionError('ONLY_ONE_EXACT_CLOSE')
                self.closed=True
            else:raise PermissionError('NOT_ALLOWED')
            kw['allow_redirects']=False
            resp=self.s.request(method,url,**kw)
            if resp.status_code//100!=2:raise RuntimeError('SIM_HTTP_'+str(resp.status_code))
            return resp
        def shutdown(self):self.s.close()
    session=ReadClose()
    c=contract(config_rest_api=cfg(base_path=HOST,api_key=creds['api_key'],api_secret=creds['secret_key'],passphrase=creds['passphrase'],session=session,timeout=8,max_retries=0))
    def read(n,q=None):return c.rest_api.execute_operation(n,{'query':q or {}}).data
    try:
        p=read('get_capi_v3_account_position_allPosition');o=read('get_capi_v3_openOrders');a=read('get_capi_v3_openAlgoOrders')
        hist=read('get_capi_v3_order_history',{'symbol':'ETHUSDT'})
        records=hist.get('orders',[]) if isinstance(hist,dict) else hist if isinstance(hist,list) else []
        matches=[x for x in records if isinstance(x,dict) and x.get('clientOrderId')==CLIENT]
        report.update(observedEntries=len(matches),positionCount=len(p),activeStops=len(a),regularOrders=len(o))
        if len(matches)==1:
            report['entryOrderId']=str(matches[0].get('orderId'))
        if proc.returncode!=73 or len(matches)!=1 or len(p)!=1 or o!=[] or len(a)!=1 or not isinstance(p[0].get('id'),int):
            report['status']='REVIEW_REQUIRED_BEFORE_CLOSE';save(report);return report
        if p[0].get('symbol')!='ETHUSDT' or p[0].get('side')!='LONG' or D(str(p[0].get('size')))!=D('0.002'):
            report['status']='UNEXPECTED_POSITION';save(report);return report
        proof=protected_entry({'entry':{'symbol':'ETHUSDT','side':'BUY','positionSide':'LONG','type':'MARKET','quantity':'0.002','newClientOrderId':CLIENT,'slTriggerPrice':report['childState']['stopPrice'],'SlWorkingType':'MARK_PRICE'}},matches[0],a,'LONG','0.002')
        report['stopVerified']=proof.get('verified') is True
        report['exactEntryVerified']=matches[0].get('status')=='FILLED'
        report['noDuplicateEntry']=len(matches)==1
        if not report['stopVerified']:
            report['status']='STOP_NOT_CERTIFIED_NEEDS_REVIEW';save(report);return report
        # Route the exact SIM close through the production supervisor tick,
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
        save(report);return report
    except Exception as e:
        report['status']='DEMO_REQUIRES_REVIEW';report['errorType']=type(e).__name__;save(report);return report
    finally:session.shutdown()
if __name__=='__main__':
    try:print(json.dumps(main()))
    except Exception as e:print(json.dumps({'status':'PRECHECK_ERROR','error':type(e).__name__}))
