"""Readback-only real recovery verifier tests; no WEEX network."""
import copy,unittest
from weex_supervised_real_recovery_v3 import classify,RecoveryBlocked
class ExchangeRecovery(unittest.TestCase):
 def setUp(self):
  self.cid='wxentry_v2_test'
  self.entry={'symbol':'ETHUSDT','side':'BUY','positionSide':'LONG',
    'type':'MARKET','quantity':'0.001','newClientOrderId':self.cid,
    'slTriggerPrice':'2088.20','SlWorkingType':'MARK_PRICE'}
  self.history=[{'symbol':'ETHUSDT','clientOrderId':self.cid,'orderId':'128',
    'status':'FILLED','side':'BUY','positionSide':'LONG','executedQty':'0.001'}]
  self.stops=[{'symbol':'ETHUSDT','positionSide':'LONG','side':'SELL',
    'quantity':'0.001','triggerPrice':'2088.20','reduceOnly':True,
    'orderType':'STOP_MARKET','algoStatus':'NEW','workingType':'MARK_PRICE',
    'algoId':'555','clientAlgoId':self.cid+'sl','actualOrderId':'128'}]
  self.positions=[{'symbol':'ETHUSDT','id':'77','side':'LONG','size':'0.001'}]
  self.regular=[]
  self.conditional=copy.deepcopy(self.stops)
 def verify(self):
  return classify(entry=self.entry,history=self.history,
   stop_orders=self.stops,positions=self.positions,
   regular_orders=self.regular,conditional_orders=self.conditional)
 def test_exact_live_shape_is_read_only_and_close_unapproved(self):
  result=self.verify()
  self.assertEqual(result['status'],'VERIFIED_PROTECTED_NEED_EXACT_CLOSE')
  self.assertEqual(result['positionId'],'77')
  self.assertFalse(result['closeAuthorized'])
  self.assertFalse(result['entryRetriesAllowed'])
  self.assertEqual(result['exchangeWrites'],0)
 def test_duplicate_entry_is_not_trusted(self):
  self.history.append(copy.deepcopy(self.history[0]))
  with self.assertRaisesRegex(RecoveryBlocked,'AMBIGUOUS'):self.verify()
 def test_missing_exchange_entry_is_not_trusted(self):
  self.history=[]
  with self.assertRaisesRegex(RecoveryBlocked,'MISSING'):self.verify()
 def test_unfilled_entry_is_not_trusted(self):
  self.history[0]['status']='PARTIALLY_FILLED'
  with self.assertRaisesRegex(RecoveryBlocked,'FULL_FILL'):self.verify()
 def test_mismatched_qty_is_not_trusted(self):
  self.positions[0]['size']='0.002'
  with self.assertRaisesRegex(RecoveryBlocked,'POSITION_SIZE'):self.verify()
 def test_stop_missing_is_not_trusted(self):
  self.stops=[]
  with self.assertRaisesRegex(RecoveryBlocked,'ATTACHED_STOP'):self.verify()
 def test_unlinked_stop_is_not_trusted(self):
  self.stops[0]['actualOrderId']='129'
  with self.assertRaisesRegex(RecoveryBlocked,'ATTACHED_STOP'):self.verify()
 def test_stop_without_reduce_only_rejected(self):
  self.stops[0]['reduceOnly']=False
  with self.assertRaisesRegex(RecoveryBlocked,'ATTACHED_STOP'):self.verify()
 def test_stop_trigger_changed_rejected(self):
  self.stops[0]['triggerPrice']='2044.00'
  with self.assertRaisesRegex(RecoveryBlocked,'ATTACHED_STOP'):self.verify()
 def test_position_missing_rejected(self):
  self.positions=[]
  with self.assertRaisesRegex(RecoveryBlocked,'EXACT_OPEN_POSITION'):self.verify()
 def test_unexpected_order_rejected(self):
  self.regular.append({'symbol':'ETHUSDT','orderId':'987'})
  with self.assertRaisesRegex(RecoveryBlocked,'UNEXPECTED_REGULAR'):self.verify()
 def test_unexpected_conditional_rejected(self):
  self.conditional.append(copy.deepcopy(self.conditional[0]))
  with self.assertRaisesRegex(RecoveryBlocked,'UNEXPECTED_ADDITIONAL'):self.verify()
 def test_no_mark_stop_in_persistent_intent_rejected(self):
  self.entry.pop('slTriggerPrice')
  with self.assertRaisesRegex(RecoveryBlocked,'ATOMIC_MARK_STOP'):self.verify()
if __name__=='__main__':unittest.main()
