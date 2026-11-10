"""Fail-closed WEEX TP LIMIT + SL compatibility tests. No network."""
import unittest
from weex_tp_limit_sl_guard import assess,residual_check

P={'symbol':'ETHUSDT','side':'LONG','size':'2'}
L={'symbol':'ETHUSDT','positionSide':'LONG','side':'SELL','reduceOnly':True,
   'type':'LIMIT','timeInForce':'GTC','origQty':'2','remainingQty':'2'}
S={'symbol':'ETHUSDT','positionSide':'LONG','side':'SELL','reduceOnly':True,
   'orderType':'STOP_MARKET','algoStatus':'UNTRIGGERED','quantity':'2'}
class Tests(unittest.TestCase):
 def test_no_evidence_blocks(self):
  self.assertEqual(assess(P,L,S)['reason'],'ACCOUNT_EVIDENCE_NOT_FRESH')
 def test_fresh_but_uncertified_blocks(self):
  a=assess(P,L,S,fresh_account_evidence=True)
  self.assertEqual(a['reason'],'SIMULTANEOUS_COVERAGE_NOT_CERTIFIED')
  self.assertFalse(a['liveEntryAllowed'])
 def test_explicit_certification_still_no_live(self):
  a=assess(P,L,S,fresh_account_evidence=True,exchange_verified_shared_coverage=True)
  self.assertFalse(a['dispatchAllowed'])
  self.assertFalse(a['stopProtectionVerified'])
 def test_partial_stop_coverage_blocks(self):
  a=assess(P,L,{**S,'quantity':'1'},fresh_account_evidence=True)
  self.assertEqual(a['reason'],'FULL_POSITION_COVERAGE_NOT_OBSERVED')
 def test_unrelated_stop_blocks(self):
  a=assess(P,L,{**S,'symbol':'BTCUSDT'})
  self.assertEqual(a['reason'],'ORDER_NOT_BOUND_TO_POSITION')
 def test_wrong_side_blocks(self):
  a=assess(P,L,{**S,'side':'BUY'})
  self.assertEqual(a['reason'],'ORDER_NOT_BOUND_TO_POSITION')
 def test_stop_not_active_blocks(self):
  a=assess(P,L,{**S,'algoStatus':'FILLED'})
  self.assertEqual(a['reason'],'STOP_NOT_ACTIVE')
 def test_remaining_equal_is_not_safety_certification(self):
  a=residual_check(P,L,S)
  self.assertEqual(a['state'],'QUANTITIES_MATCH_NOT_CERTIFIED')
  self.assertFalse(a['stopProtectionVerified'])
 def test_partial_fill_quantity_disagreement(self):
  a=residual_check({**P,'size':'1'},{**L,'remainingQty':'1'},S)
  self.assertEqual(a['reason'],'EXIT_QUANTITY_NOT_SYNCHRONIZED')
 def test_position_closed_orders_still_present(self):
  a=residual_check({**P,'size':'0'},L,S)
  self.assertEqual(a['reason'],'STALE_CLOSING_ORDERS_AFTER_CLOSE')
 def test_zero_position_zero_orders(self):
  a=residual_check({**P,'size':'0'},{**L,'remainingQty':'0'},{**S,'quantity':'0'})
  self.assertEqual(a['state'],'CLOSED_OBSERVED')
 def test_invalid_quantities_block(self):
  a=residual_check(P,{**L,'remainingQty':'-1'},S)
  self.assertEqual(a['state'],'REVIEW_REQUIRED')
if __name__=='__main__':unittest.main()
