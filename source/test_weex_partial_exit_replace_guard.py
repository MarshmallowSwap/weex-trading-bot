import unittest
from weex_partial_exit_replace_guard import inspect
P={'id':123,'symbol':'BTCUSDT','side':'LONG','size':'0.0001'}
def order(cid,qty,typ,oid):
 return {'algoId':oid,'clientAlgoId':cid,'symbol':'BTCUSDT','positionSide':'LONG',
         'side':'SELL','reduceOnly':True,'algoStatus':'UNTRIGGERED',
         'quantity':qty,'orderType':typ}
OTP=order('tpold','.0002','TAKE_PROFIT_LIMIT',11)
OSL=order('slold','.0002','STOP_LOSS_MARKET',12)
NSL=order('slnew','.0001','STOP_LOSS_MARKET',13)
NTP=order('tpnew','.0001','TAKE_PROFIT_LIMIT',14)
class Tests(unittest.TestCase):
 def check(self,algos=None,position=None,regular_orders=None):
  return inspect(position=P if position is None else position,
     algos=[OTP,OSL] if algos is None else algos,
     regular_orders=[] if regular_orders is None else regular_orders,
     expected_position_id=123,old_tp_client='tpold',old_sl_client='slold',
     new_tp_client='tpnew',new_sl_client='slnew')
 def test_partial_prioritizes_stop_first(self):
  r=self.check();self.assertEqual(r['status'],'NEEDS_NEW_STOP_FIRST_OFFLINE')
  self.assertTrue(r['originalSlOversized']);self.assertFalse(r['allowedToSend'])
 def test_new_stop_before_cancel(self):
  r=self.check(algos=[OTP,OSL,NSL])
  self.assertEqual(r['status'],'DUPLICATE_STOPS_REVIEW')
  self.assertFalse(r['allowedToCancel'])
 def test_old_stop_removed_old_tp_pending(self):
  r=self.check(algos=[OTP,NSL])
  self.assertEqual(r['status'],'NEW_STOP_ONLY_OLD_TP_REVIEW')
 def test_new_stop_only_needs_tp(self):
  r=self.check(algos=[NSL])
  self.assertEqual(r['status'],'NEW_STOP_PRESENT_TP_MISSING')
 def test_replacement_pair_not_live_certified(self):
  r=self.check(algos=[NSL,NTP])
  self.assertEqual(r['status'],'PAIR_RESTORED_OFFLINE_ONLY')
  self.assertFalse(r['stopCoverageCertified'])
  self.assertFalse(r['liveEnabled'])
 def test_no_stop_fail_closed(self):
  r=self.check(algos=[OTP])
  self.assertEqual(r['reason'],'STOP_LOSS_MISSING')
 def test_wrong_new_stop_qty(self):
  r=self.check(algos=[OSL,{**NSL,'quantity':'.0002'}])
  self.assertEqual(r['reason'],'NEW_STOP_QUANTITY_NOT_RESIDUAL')
 def test_new_stop_not_reduce_only(self):
  r=self.check(algos=[OSL,{**NSL,'reduceOnly':False}])
  self.assertEqual(r['reason'],'INVALID_NEW_SL_EVIDENCE')
 def test_order_duplicate(self):
  r=self.check(algos=[OTP,OSL,OSL])
  self.assertEqual(r['reason'],'DUPLICATE_OLD_SL')
 def test_position_changed(self):
  r=self.check(position={**P,'id':999})
  self.assertEqual(r['reason'],'POSITION_ID_CHANGED')
 def test_regular_order_active_blocks(self):
  r=self.check(regular_orders=[{'symbol':'BTCUSDT'}])
  self.assertEqual(r['reason'],'ACTIVE_REGULAR_ORDER_REQUIRES_RECONCILIATION')
 def test_unknown_algo_same_symbol_blocks(self):
  unknown={**OSL,'algoId':999,'clientAlgoId':'untracked'}
  self.assertEqual(self.check(algos=[OTP,OSL,unknown])['reason'],'UNKNOWN_ALGO_FOR_POSITION_SYMBOL')
 def test_unknown_algo_other_symbol_does_not_block(self):
  other={**OSL,'algoId':999,'clientAlgoId':'untracked','symbol':'ETHUSDT'}
  self.assertEqual(self.check(algos=[OTP,OSL,other])['status'],'NEEDS_NEW_STOP_FIRST_OFFLINE')
 def test_no_position_block(self):
  r=self.check(position={**P,'size':'0'})
  self.assertEqual(r['reason'],'NO_OPEN_POSITION')
if __name__=='__main__':unittest.main()
