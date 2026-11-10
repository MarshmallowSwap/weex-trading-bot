"""GET-only limit adapter tests, injected fake exchange."""
import tempfile,unittest
from pathlib import Path
from weex_tp_limit_shadow import propose
from weex_tp_limit_journal import register
from weex_tp_limit_readonly import inspect,reconcile

class Fake:
 def __init__(self,p):
  r=p['request'];self.order={'orderId':'o1','clientOrderId':r['newClientOrderId'],
    'symbol':r['symbol'],'side':r['side'],'positionSide':r['positionSide'],
    'type':'LIMIT','timeInForce':'GTC','price':r['price'],'origQty':r['quantity'],
    'reduceOnly':True,'status':'NEW','executedQty':'0'}
  self.positions=[{'symbol':r['symbol'],'side':r['positionSide'],'size':r['quantity']}]
  self.fills=[];self.present=True;self.calls=[]
 def __call__(self,op,**q):
  self.calls.append(op)
  if op=='get_capi_v3_openOrders':return [self.order] if self.present and self.order['status']=='NEW' else []
  if op=='get_capi_v3_order_history':return [self.order] if self.present else []
  if op=='get_capi_v3_account_position_allPosition':return self.positions
  if op=='get_capi_v3_openAlgoOrders':return []
  if op=='get_capi_v3_userTrades':return self.fills
  raise AssertionError('WRONG_READ_'+op)
class Tests(unittest.TestCase):
 def setUp(self):
  tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
  self.path=Path(tmp.name)/'shadow.db';self.tid='wxentry_example123'
  self.p=propose(trade_id=self.tid,symbol='ETHUSDT',position_id='p1',
    side='LONG',quantity='2',entry_cost_usdt='200',entry_fees_usdt='.16',
    exit_fee_rate='.0008',target_net_usdt='5',price_tick='.01',
    position_observation={'id':'p1','symbol':'ETHUSDT','side':'LONG',
      'size':'2','openValue':'200','openFee':'.16'},regular_orders=[],conditional_orders=[])
  self.fake=Fake(self.p)
 def test_unfilled_matching_order(self):
  register(self.path,self.tid,self.p)
  report=reconcile(self.fake,self.path,self.tid,self.p,now_ms=1000000)
  self.assertEqual(report['journalState'],'OPEN_UNFILLED')
  self.assertFalse(report['protectiveStopConfirmed'])
  self.assertTrue(all(x.startswith('get_') for x in self.fake.calls))
 def test_missing_order_never_retries(self):
  self.fake.present=False
  report=inspect(self.fake,self.p,now_ms=1000000)
  self.assertEqual(report['state'],'NO_MATCHING_EXCHANGE_ORDER')
  self.assertFalse(report['canRetry'])
 def test_changed_price_blocks(self):
  self.fake.order['price']='1'
  self.assertEqual(inspect(self.fake,self.p,now_ms=1000000)['state'],'REVIEW_REQUIRED')
 def test_partial_fill_reconciled(self):
  register(self.path,self.tid,self.p)
  self.fake.order.update(executedQty='1',status='PARTIALLY_FILLED')
  self.fake.positions[0]['size']='1'
  self.fake.fills=[{'id':'f1','orderId':'o1','symbol':'ETHUSDT','side':'SELL',
    'positionSide':'LONG','qty':'1','price':self.fake.order['price'],
    'commission':'0.084','commissionAsset':'USDT'}]
  self.assertEqual(reconcile(self.fake,self.path,self.tid,self.p,now_ms=1000000)['journalState'],'PARTIALLY_FILLED')
 def test_duplicate_order_blocks(self):
  old=self.fake.__call__
  class Duplicate:
   def __call__(_,op,**q):
    v=old(op,**q)
    if op=='get_capi_v3_order_history':return v+[{**v[0],'orderId':'o2'}]
    return v
  self.assertEqual(inspect(Duplicate(),self.p,now_ms=1000000)['state'],'REVIEW_REQUIRED')
 def test_position_mismatch_blocks(self):
  self.fake.positions[0]['size']='1'
  self.assertEqual(inspect(self.fake,self.p,now_ms=1000000)['state'],'REVIEW_REQUIRED')
 def test_read_failure_no_write(self):
  def broken(op,**q):raise RuntimeError('network unavailable')
  self.assertEqual(inspect(broken,self.p,now_ms=1000000)['state'],'READ_UNAVAILABLE')

if __name__=='__main__':unittest.main()
