"""Mock authenticated SDK reads. Verify real recovery adapter never POSTs."""
import unittest,copy
from unittest.mock import patch
from weex_supervised_real_recovery_v3 import read_exchange,RecoveryBlocked
class ReaderCase(unittest.TestCase):
 def setUp(self):
  self.id='wxentry_v2_demo'
  self.entry={'symbol':'ETHUSDT','side':'BUY','positionSide':'LONG','type':'MARKET',
    'quantity':'0.001','newClientOrderId':self.id,'slTriggerPrice':'2088.20',
    'SlWorkingType':'MARK_PRICE'}
  self.order={'symbol':'ETHUSDT','clientOrderId':self.id,'orderId':'128',
    'status':'FILLED','side':'BUY','positionSide':'LONG','executedQty':'0.001'}
  self.stop={'symbol':'ETHUSDT','positionSide':'LONG','side':'SELL',
    'quantity':'0.001','triggerPrice':'2088.20','reduceOnly':True,
    'orderType':'STOP_MARKET','algoStatus':'NEW','workingType':'MARK_PRICE',
    'algoId':'555','clientAlgoId':self.id+'sl','actualOrderId':'128'}
  self.calls=[]
 def read(self,op,**kwargs):
  self.calls.append((op,kwargs))
  if op=='get_capi_v3_order_history':return [self.order]
  if op=='get_capi_v3_order':return self.order
  if op=='get_capi_v3_allAlgoOrders':return {'orders':[self.stop]}
  raise AssertionError('Unexpected read')
 def account(self):
  return ([{'symbol':'ETHUSDT','id':'77','side':'LONG','size':'0.001'}],[],[self.stop])
 def execute(self):
  with patch('weex_supervised_real_recovery_v3.prove_unknown_intent',return_value=self.entry):
   return read_exchange(self.id,reader=self)
 def test_bounded_history_then_exact_id_and_no_write(self):
  result=self.execute()
  self.assertEqual(result['status'],'VERIFIED_PROTECTED_NEED_EXACT_CLOSE')
  self.assertFalse(result['closeAuthorized'])
  self.assertEqual(result['exchangeWrites'],0)
  self.assertEqual([x[0] for x in self.calls],[
   'get_capi_v3_order_history','get_capi_v3_order','get_capi_v3_allAlgoOrders'])
  self.assertEqual(self.calls[1][1],{'orderId':'128'})
 def test_missing_history_fail_closed(self):
  original=self.read
  def changed(op,**kw):
   if op=='get_capi_v3_order_history':return []
   return original(op,**kw)
  self.read=changed
  with self.assertRaisesRegex(RecoveryBlocked,'MISSING_OR_AMBIGUOUS'):self.execute()
 def test_duplicate_history_fail_closed(self):
  original=self.read
  def changed(op,**kw):
   if op=='get_capi_v3_order_history':return [self.order,dict(self.order,orderId='129')]
   return original(op,**kw)
  self.read=changed
  with self.assertRaisesRegex(RecoveryBlocked,'MISSING_OR_AMBIGUOUS'):self.execute()
 def test_changed_exact_order_fail_closed(self):
  original=self.read
  def changed(op,**kw):
   if op=='get_capi_v3_order':return dict(self.order,orderId='129')
   return original(op,**kw)
  self.read=changed
  with self.assertRaisesRegex(RecoveryBlocked,'EXACT_ORDER_LOOKUP_FAILED'):self.execute()
if __name__=='__main__':unittest.main()
