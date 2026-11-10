import unittest
from weex_pilot_exit_stop_lifecycle import assess
P={'symbol':'ETHUSDT','id':'123','side':'LONG','size':'0.002','marginType':'ISOLATED'}
S={'algoId':'ABC','symbol':'ETHUSDT','positionSide':'LONG','side':'SELL',
   'orderType':'STOP_MARKET','algoStatus':'UNTRIGGERED','reduceOnly':True,
   'closePosition':True,'quantity':'0','triggerPrice':'2110'}
class Lifecycle(unittest.TestCase):
 def test_no_stop_allows_only_fresh_dispatch_preflight(self):
  x=assess(positions=[P],regular=[],conditional=[],expected_position=P)
  self.assertTrue(x['readyToDispatchEmergency']);self.assertTrue(x['requiresFreshReadbackBeforeDispatch'])
 def test_active_stop_requires_cancel_and_readback(self):
  x=assess(positions=[P],regular=[],conditional=[S],expected_position=P,
           expected_stop={'algoId':'ABC','triggerPrice':'2110'})
  self.assertFalse(x['readyToDispatchEmergency']);self.assertEqual(x['exactAlgoId'],'ABC')
  self.assertFalse(x['canCancel'])
 def test_unrelated_stop_rejected(self):
  x=assess(positions=[P],regular=[],conditional=[S],expected_position=P,
           expected_stop={'algoId':'OTHER','triggerPrice':'2110'})
  self.assertEqual(x['reason'],'CONDITIONAL_STOP_NOT_UNIQUELY_OWNED_ACTIVE')
 def test_wrong_position_rejected(self):
  x=assess(positions=[{**P,'id':'222'}],regular=[],conditional=[],
           expected_position=P)
  self.assertFalse(x['readyToDispatchEmergency'])
 def test_flat_orphan_requires_cancel(self):
  x=assess(positions=[],regular=[],conditional=[S],expected_stop={'algoId':'ABC'})
  self.assertEqual(x['reason'],'ACCOUNT_FLAT_RESIDUAL_STOP_NEEDS_EXACT_CANCEL_READBACK')
  self.assertFalse(x['canCancel'])
 def test_flat_clean(self):
  x=assess(positions=[],regular=[],conditional=[])
  self.assertTrue(x['flatVerified'])
 def test_no_overlapping_regular_orders(self):
  x=assess(positions=[P],regular=[{'symbol':'ETHUSDT'}],conditional=[],
           expected_position=P)
  self.assertFalse(x['readyToDispatchEmergency'])
 def test_wrong_trigger_rejected(self):
  x=assess(positions=[P],regular=[],conditional=[S],expected_position=P,
           expected_stop={'algoId':'ABC','triggerPrice':'2000'})
  self.assertEqual(x['reason'],'STOP_TRIGGER_PRICE_NOT_EXACT')
if __name__=='__main__':unittest.main()
