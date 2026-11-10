"""One-time TP repair only when guarded gateway proves original request never sent."""
import tempfile,copy,unittest
from pathlib import Path
from weex_lifecycle import Lifecycle,now
from test_weex_lifecycle import Exchange,CFG,PLAN
from weex_tp_local_notsent_repair import marker,eligible

class Fake(Exchange):
 def __init__(self):
  super().__init__();self.tp_attempts=0;self.tp_failures=1
 def write(self,op,p):
  if op=='post_capi_v3_placeTpSlOrder':
   self.tp_attempts+=1
   if self.tp_attempts<=self.tp_failures:
    return [{'success':False,'localNotSent':True,'reason':'BLOCKED_BEFORE_NETWORK'}]
  return super().write(op,p)
class Repair(unittest.TestCase):
 def setUp(self):
  t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup)
  self.fake=Fake();self.cfg=copy.deepcopy(CFG)
  self.cfg['strategySettings'].update(targetNetProfitUSDT=20,tpAccountingMode='GROSS_BEFORE_COSTS')
  self.p=copy.deepcopy(PLAN);self.p.update(targetNetProfitUSDT='20',tpAccountingMode='GROSS_BEFORE_COSTS')
  self.engine=Lifecycle(Path(t.name)/'db.sqlite3',self.fake,lambda:self.cfg)
  self.id=self.engine.prepare('test-repair',self.p)['id']
 def context(self,symbol):
  return {'observedAtMs':now(),'complete':True,'apiEnabled':True,'accountCanTrade':True,
   'hedgeMode':True,'depthUnitVerified':True,'liquidityPassed':True,
   'marketSignal':'LONG','riskTierVerified':True,'availableBalance':'100',
   'positions':[],'openOrders':[],'conditionalOrders':[],
   'symbolConfig':{'symbol':symbol,'marginType':self.fake.margin,'crossLeverage':self.fake.leverage},
   'referencePrice':'2500','exitFeeRate':'.0008','maximumPermittedLeverage':'100'}
 def test_safe_one_time_repair_after_local_non_submission(self):
  self.assertEqual(self.engine.advance(self.id,self.context)['state'],'TP_PENDING')
  self.assertEqual(self.fake.tp_attempts,1)
  self.assertTrue(eligible(self.engine.writes(self.id),self.engine.get(self.id)['owned']))
  self.assertEqual(self.engine.reconcile(self.id)['state'],'TP_PENDING')
  self.assertEqual(self.fake.tp_attempts,2)
  self.assertEqual(self.engine.reconcile(self.id)['state'],'PROTECTED')
  self.assertEqual(self.engine.reconcile(self.id)['state'],'PROTECTED')
  self.assertEqual(self.fake.tp_attempts,2)
 def test_both_local_non_submissions_exhaust_repair(self):
  self.fake.tp_failures=2
  self.engine.advance(self.id,self.context)
  self.assertEqual(self.engine.reconcile(self.id)['state'],'REVIEW_REQUIRED')
  self.assertEqual(self.engine.reconcile(self.id)['state'],'REVIEW_REQUIRED')
  self.assertEqual(self.fake.tp_attempts,2)
 def test_original_uncertain_never_retries(self):
  self.fake.tp_failures=0
  orig=self.fake.write
  def uncertain(op,p):
   if op=='post_capi_v3_placeTpSlOrder':
    self.fake.tp_attempts+=1;raise TimeoutError('UNCERTAIN')
   return orig(op,p)
  self.fake.write=uncertain
  self.engine.advance(self.id,self.context)
  self.assertEqual(self.engine.reconcile(self.id)['state'],'TP_PENDING')
  self.assertEqual(self.engine.reconcile(self.id)['state'],'TP_PENDING')
  self.assertEqual(self.fake.tp_attempts,1)
  self.assertNotIn('TP_REPAIR',self.engine.writes(self.id))
 def test_changed_position_blocks_repair(self):
  self.engine.advance(self.id,self.context)
  self.fake.positions[0]['size']='0.01'
  self.assertEqual(self.engine.reconcile(self.id)['state'],'REVIEW_REQUIRED')
  self.assertEqual(self.fake.tp_attempts,1)
 def test_unrelated_algo_blocks_repair(self):
  self.engine.advance(self.id,self.context)
  self.fake.algos=[{'algoId':'999','clientAlgoId':'unrelated','symbol':'ETHUSDT',
   'positionSide':'LONG','side':'SELL','orderType':'TAKE_PROFIT_MARKET',
   'reduceOnly':True,'quantity':'0.02','triggerPrice':'2600',
   'workingType':'MARK_PRICE','algoStatus':'UNTRIGGERED'}]
  self.assertEqual(self.engine.reconcile(self.id)['state'],'REVIEW_REQUIRED')
  self.assertEqual(self.fake.tp_attempts,1)
 def test_repair_sent_but_ack_lost_is_not_replayed(self):
  self.engine.advance(self.id,self.context)
  original=self.fake.write
  def ambiguous(op,p):
   if op=='post_capi_v3_placeTpSlOrder' and self.fake.tp_attempts==1:
    result=original(op,p)
    raise TimeoutError('REPAIR_ACK_LOST')
   return original(op,p)
  self.fake.write=ambiguous
  self.assertEqual(self.engine.reconcile(self.id)['state'],'TP_PENDING')
  self.assertEqual(self.fake.tp_attempts,2)
  self.assertEqual(self.engine.reconcile(self.id)['state'],'PROTECTED')
  self.assertEqual(self.fake.tp_attempts,2)
 def test_repair_timeout_before_send_is_not_replayed(self):
  self.engine.advance(self.id,self.context)
  original=self.fake.write
  def lost(op,p):
   if op=='post_capi_v3_placeTpSlOrder':
    self.fake.tp_attempts+=1
    raise TimeoutError('REPAIR_UNCERTAIN')
   return original(op,p)
  self.fake.write=lost
  self.assertEqual(self.engine.reconcile(self.id)['state'],'TP_PENDING')
  self.assertEqual(self.engine.reconcile(self.id)['state'],'TP_PENDING')
  self.assertEqual(self.fake.tp_attempts,2)
 def test_local_marker_requires_exact_origin(self):
  self.assertFalse(marker({'success':False,'reason':'BLOCKED_BEFORE_NETWORK'}))
  self.assertFalse(marker({'success':False,'localNotSent':True,'reason':'HTTP_TIMEOUT'}))
  self.assertTrue(marker([{'success':False,'localNotSent':True,'reason':'BLOCKED_BEFORE_NETWORK'}]))
if __name__=='__main__':unittest.main()
