import unittest
from weex_live_position_protection_shadow import stop_covers_position
P={'symbol':'BTCUSDT','side':'SHORT','size':'0.0100'}
A={'symbol':'BTCUSDT','positionSide':'SHORT','side':'BUY',
    'orderType':'STOP_MARKET','reduceOnly':True,'algoStatus':'UNTRIGGERED',
    'quantity':'0.01','triggerPrice':'100000'}
class StopEvidence(unittest.TestCase):
 def test_numeric_comparison_normalized(self):
  self.assertTrue(stop_covers_position(P,A))
 def test_wrong_side_fails(self):
  self.assertFalse(stop_covers_position(P,{**A,'side':'SELL'}))
 def test_wrong_position_side_fails(self):
  self.assertFalse(stop_covers_position(P,{**A,'positionSide':'LONG'}))
 def test_wrong_symbol_fails(self):
  self.assertFalse(stop_covers_position(P,{**A,'symbol':'ETHUSDT'}))
 def test_zero_trigger_fails(self):
  self.assertFalse(stop_covers_position(P,{**A,'triggerPrice':'0'}))
 def test_missing_trigger_fails(self):
  self.assertFalse(stop_covers_position(P,{k:v for k,v in A.items() if k!='triggerPrice'}))
 def test_negative_trigger_fails(self):
  self.assertFalse(stop_covers_position(P,{**A,'triggerPrice':'-5'}))
 def test_nonfinite_quantity_fails(self):
  self.assertFalse(stop_covers_position(P,{**A,'quantity':'Infinity'}))
 def test_changed_position_quantity_fails(self):
  self.assertFalse(stop_covers_position({**P,'size':'0.005'},A))
 def test_triggered_order_not_pending_protection(self):
  self.assertFalse(stop_covers_position(P,{**A,'algoStatus':'TRIGGERED'}))
 def test_non_reduce_only_fails(self):
  self.assertFalse(stop_covers_position(P,{**A,'reduceOnly':False}))
if __name__=='__main__':unittest.main()
