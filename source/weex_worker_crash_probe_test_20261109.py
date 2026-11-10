"""Offline OS-crash integration test of the actual WEEX worker Lifecycle dispatch.
Uses a durable fake exchange in a temporary directory; no credentials or HTTP.
The production Gateway never defines _test_crash_after_entry_ack.
"""
import copy,json,os,subprocess,sys,tempfile
from pathlib import Path
from weex_full_lifecycle_os_crash_drill import DurableFakeExchange
from test_weex_lifecycle import CFG,PLAN
from weex_lifecycle import Lifecycle,now
import live_control

CHILD=r'''
import copy,os,sys
from pathlib import Path
from weex_full_lifecycle_os_crash_drill import DurableFakeExchange
from test_weex_lifecycle import CFG,PLAN
from weex_lifecycle import Lifecycle,now
folder=Path(sys.argv[1])
fake=DurableFakeExchange(folder/'fake_exchange.json')
def crash(tid,op,payload,ack):
    assert op=='post_capi_v3_order'
    assert ack.get('orderId')=='1'
    os._exit(79)
fake._test_crash_after_entry_ack=crash
engine=Lifecycle(folder/'journal.sqlite3',fake,lambda:copy.deepcopy(CFG))
item=engine.prepare('integrated-worker-crash-check',copy.deepcopy(PLAN))
def context(symbol):
    return {'observedAtMs':now(),'complete':True,'apiEnabled':True,'accountCanTrade':True,'hedgeMode':True,
        'depthUnitVerified':True,'liquidityPassed':True,'marketSignal':'LONG','riskTierVerified':True,
        'availableBalance':'100','positions':[],'openOrders':[],'conditionalOrders':[],
        'symbolConfig':{'symbol':symbol,'marginType':fake.margin,'crossLeverage':fake.leverage},
        'referencePrice':'2500','exitFeeRate':'0.0008','maximumPermittedLeverage':'100'}
engine.advance(item['id'],context)
raise AssertionError('CRASH_NOT_TRIGGERED')
'''

def run():
    if live_control.state()['mode']!='STOPPED':
        raise PermissionError('PRODUCTION_MUST_BE_STOPPED')
    from weex_live_worker import Gateway
    from weex_lifecycle import SDKGateway
    assert not hasattr(Gateway,'_test_crash_after_entry_ack')
    assert not hasattr(SDKGateway,'_test_crash_after_entry_ack')
    with tempfile.TemporaryDirectory(prefix='weex_actual_worker_probe_') as tmp:
        folder=Path(tmp)
        child=subprocess.run([sys.executable,'-B','-c',CHILD,str(folder)],cwd=Path(__file__).resolve().parent,
                             capture_output=True,text=True,timeout=20)
        assert child.returncode==79,(child.returncode,child.stderr[-400:])
        fake=DurableFakeExchange(folder/'fake_exchange.json')
        engine=Lifecycle(folder/'journal.sqlite3',fake,lambda:copy.deepcopy(CFG))
        states=engine.states()
        assert len(states)==1
        tid=states[0]['id']
        writes=engine.writes(tid)
        assert writes['ENTRY']['state']=='UNKNOWN'
        before=sum(x[0]=='post_capi_v3_order' for x in fake.calls)
        assert before==1
        attempted=engine.send_once(tid,'ENTRY','post_capi_v3_order',engine.get(tid)['plan']['entry'],
                                  capacity={'count':0,'symbols':[]})
        assert attempted['state']=='RECONCILE_NO_RETRY'
        result=engine.reconcile(tid)
        if result['state']=='TP_PENDING':result=engine.reconcile(tid)
        after=sum(x[0]=='post_capi_v3_order' for x in fake.calls)
        assert before==after==1
        assert result['state']=='PROTECTED',result
        return {'status':'PASS','childExitCode':child.returncode,
                'durableIntentBeforeCrash':'UNKNOWN','entriesBeforeAndAfterRestart':[before,after],
                'duplicateEntries':after-before,'recoveredState':result['state'],
                'productionGatewayHasCrashHook':False,'liveOrders':0,'networkRequests':0}

if __name__=='__main__':
    print(json.dumps(run(),ensure_ascii=False))
