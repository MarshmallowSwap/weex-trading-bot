"""Real Windows process termination during a fully simulated WEEX lifecycle.

The mock exchange persists exchange state to a separate disk file *before*
abruptly terminating the child process. On a new process, lifecycle.readback
must discover the existing entry/TP, not dispatch a duplicate.
No WEEX credentials, HTTP, network or real order access.
"""
import copy,json,os,subprocess,sys,tempfile
from pathlib import Path
from test_weex_lifecycle import Exchange,CFG,PLAN
from weex_lifecycle import Lifecycle

class DurableFakeExchange(Exchange):
 def __init__(self,path,crash_op=None,crash_before=False):
  super().__init__()
  self.path=Path(path);self.crash_op=crash_op;self.crash_before=crash_before
  if self.path.exists():
   d=json.loads(self.path.read_text(encoding='utf8'))
   for k in ('calls','order','trades','positions','algos','margin','leverage','partial','cancelled'):
    setattr(self,k,d[k])
 def persist(self):
  d={k:getattr(self,k) for k in ('calls','order','trades','positions','algos','margin','leverage','partial','cancelled')}
  t=self.path.with_suffix('.tmp')
  t.write_text(json.dumps(d),encoding='utf8')
  os.replace(t,self.path)
 def write(self,op,p):
  if op==self.crash_op and self.crash_before:
   os._exit(77)
  result=super().write(op,p)
  self.persist()
  if op==self.crash_op:os._exit(77)
  return result

CHILD=r'''
import sys,copy
from pathlib import Path
from weex_full_lifecycle_os_crash_drill import DurableFakeExchange
from test_weex_lifecycle import CFG,PLAN
from weex_lifecycle import Lifecycle,now
root=Path(sys.argv[1]);point=sys.argv[2]
op='post_capi_v3_order' if 'ENTRY' in point else 'post_capi_v3_placeTpSlOrder'
e=DurableFakeExchange(root/'mock_exchange.json',crash_op=op,crash_before=point.endswith('BEFORE_SEND'))
c=copy.deepcopy(CFG);c['strategySettings']['targetNetProfitUSDT']=20;c['strategySettings']['tpAccountingMode']='GROSS_BEFORE_COSTS'
p=copy.deepcopy(PLAN);p.update(targetNetProfitUSDT='20',tpAccountingMode='GROSS_BEFORE_COSTS')
engine=Lifecycle(root/'journal.sqlite3',e,lambda:c);item=engine.prepare('crash-1',p)
def context(symbol):
 return {'observedAtMs':now(),'complete':True,'apiEnabled':True,'accountCanTrade':True,'hedgeMode':True,
 'depthUnitVerified':True,'liquidityPassed':True,'marketSignal':'LONG','riskTierVerified':True,
 'availableBalance':'100','positions':[],'openOrders':[],'conditionalOrders':[],
 'symbolConfig':{'symbol':symbol,'marginType':e.margin,'crossLeverage':e.leverage},
 'referencePrice':'2500','exitFeeRate':'.0008','maximumPermittedLeverage':'100'}
engine.advance(item['id'],context)
raise AssertionError('CRASH_NOT_REACHED')
'''

def run():
 import live_control
 root=Path(__file__).resolve().parent
 if live_control.state(root)['mode']!='STOPPED':raise PermissionError('LIVE_NOT_STOPPED')
 results=[]
 for point in ('ENTRY_BEFORE_SEND','ENTRY_AFTER_SEND','TP_BEFORE_SEND','TP_AFTER_SEND'):
  with tempfile.TemporaryDirectory(prefix='weex_full_lifecycle_crash_') as t:
   folder=Path(t)
   child=subprocess.run([sys.executable,'-c',CHILD,t,point],
      cwd=str(root),capture_output=True,text=True,timeout=20)
   if child.returncode!=77:
    raise AssertionError('UNEXPECTED_CHILD_EXIT_'+point+':'+str(child.returncode)+':'+child.stderr[-300:])
   fake=DurableFakeExchange(folder/'mock_exchange.json')
   from weex_lifecycle import now
   c=copy.deepcopy(CFG);c['strategySettings']['targetNetProfitUSDT']=20
   c['strategySettings']['tpAccountingMode']='GROSS_BEFORE_COSTS'
   engine=Lifecycle(folder/'journal.sqlite3',fake,lambda:c)
   trade=engine.states()
   if len(trade)!=1:raise AssertionError('JOURNAL_MISSING_'+point)
   tid=trade[0]['id']
   before_entry=sum(x[0]=='post_capi_v3_order' for x in fake.calls)
   before_tp=sum(x[0]=='post_capi_v3_placeTpSlOrder' for x in fake.calls)
   def context(symbol):
    return {'observedAtMs':now(),'complete':True,'apiEnabled':True,'accountCanTrade':True,'hedgeMode':True,
     'depthUnitVerified':True,'liquidityPassed':True,'marketSignal':'LONG','riskTierVerified':True,
     'availableBalance':'100','positions':[],'openOrders':[],'conditionalOrders':[],
     'symbolConfig':{'symbol':symbol,'marginType':fake.margin,'crossLeverage':fake.leverage},
     'referencePrice':'2500','exitFeeRate':'.0008','maximumPermittedLeverage':'100'}
   outcome=engine.advance(tid,context)
   recovered=engine.reconcile(tid)
   after_entry=sum(x[0]=='post_capi_v3_order' for x in fake.calls)
   after_tp=sum(x[0]=='post_capi_v3_placeTpSlOrder' for x in fake.calls)
   if after_entry>1 or after_tp>1:raise AssertionError('DUPLICATE_EXCHANGE_WRITE_'+point)
   if point=='ENTRY_BEFORE_SEND' and after_entry!=0:
    raise AssertionError('UNVERIFIED_ENTRY_RETRIED')
   if point=='ENTRY_AFTER_SEND' and (before_entry!=1 or after_entry!=1):
    raise AssertionError('ENTRY_REPLAYED')
   if point=='TP_AFTER_SEND' and (before_entry!=1 or before_tp!=1 or after_tp!=1):
    raise AssertionError('TP_REPLAYED')
   results.append({'crashPoint':point,'beforeEntryWrites':before_entry,
    'afterEntryWrites':after_entry,'beforeTpWrites':before_tp,'afterTpWrites':after_tp,
    'postRestartState':recovered['state'],'noDuplicateWrite':True})
 return {'status':'FULL_LIFECYCLE_OS_CRASH_SIMULATED_EXCHANGE',
 'results':results,'realWEEXCrashTested':False,'exchangeWrites':0,'liveMode':'STOPPED'}
if __name__=='__main__':print(json.dumps(run(),indent=2))
