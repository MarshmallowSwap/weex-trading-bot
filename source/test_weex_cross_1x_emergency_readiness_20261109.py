import unittest
from weex_cross_1x_emergency_readiness_20261109 import assess
I={'symbol':'ETHUSDT','side':'BUY','positionSide':'LONG','type':'MARKET',
 'quantity':'0.002','newClientOrderId':'wxpilot_test_01'}
E={'clientOrderId':'wxpilot_test_01','orderId':'101','symbol':'ETHUSDT',
 'positionSide':'LONG','status':'FILLED','executedQty':'0.002','avgPrice':'2100'}
P={'id':'201','symbol':'ETHUSDT','side':'LONG','marginType':'CROSSED',
 'separatedMode':'COMBINED','leverage':'1','size':'0.002'}
S={'algoId':'301','symbol':'ETHUSDT','positionSide':'LONG','side':'SELL',
 'reduceOnly':True,'algoStatus':'NEW','orderType':'STOP_MARKET',
 'workingType':'MARK_PRICE','quantity':'0.002','triggerPrice':'2060',
 'clientAlgoId':'wxpilot_test_01sl','actualOrderId':'101'}
class ClosePlan(unittest.TestCase):
 def runcheck(self,**kwargs):
  arg={'intent':I,'entry':E,'positions':[P],
   'regular_orders':[],'conditional':[S],'exchange_cross_leverage':'1'}
  arg.update(kwargs)
  return assess(**arg)
 def test_exact_preview(self):
  r=self.runcheck()
  self.assertTrue(r['readyForSupervisedClose'])
  self.assertEqual(r['closePayloadPreview'],{'symbol':'ETHUSDT','positionId':201})
  self.assertFalse(r['maySendOrder'])
 def test_no_stop(self):self.assertFalse(self.runcheck(conditional=[])['readyForSupervisedClose'])
 def test_wrong_position(self):self.assertFalse(self.runcheck(positions=[{**P,'id':'202','size':'0.003'}])['readyForSupervisedClose'])
 def test_isolated_rejected(self):self.assertFalse(self.runcheck(positions=[{**P,'marginType':'ISOLATED'}])['readyForSupervisedClose'])
 def test_unconfirmed_margin(self):self.assertFalse(self.runcheck(exchange_cross_leverage='125')['readyForSupervisedClose'])
 def test_wrong_stop_parent(self):self.assertFalse(self.runcheck(conditional=[{**S,'actualOrderId':'102'}])['readyForSupervisedClose'])
 def test_wrong_stop_size(self):self.assertFalse(self.runcheck(conditional=[{**S,'quantity':'0.01'}])['readyForSupervisedClose'])
 def test_non_reduce_stop(self):self.assertFalse(self.runcheck(conditional=[{**S,'reduceOnly':False}])['readyForSupervisedClose'])
 def test_expired_stop(self):self.assertFalse(self.runcheck(conditional=[{**S,'algoStatus':'CANCELED'}])['readyForSupervisedClose'])
 def test_stop_above_entry(self):self.assertFalse(self.runcheck(conditional=[{**S,'triggerPrice':'2200'}])['readyForSupervisedClose'])
 def test_notional_above_five(self):self.assertFalse(self.runcheck(entry={**E,'avgPrice':'2700'})['readyForSupervisedClose'])
 def test_foreign_order(self):self.assertFalse(self.runcheck(regular_orders=[{'symbol':'BTCUSDT'}])['readyForSupervisedClose'])
 def test_second_position(self):self.assertFalse(self.runcheck(positions=[P,{**P,'id':'202'}])['readyForSupervisedClose'])
 def test_missing_account_readback(self):self.assertFalse(self.runcheck(account_read_complete=False)['readyForSupervisedClose'])
 def test_bot_running(self):self.assertFalse(self.runcheck(main_bot_stopped=False)['readyForSupervisedClose'])
 def test_bad_id(self):self.assertFalse(self.runcheck(positions=[{**P,'id':'unknown'}])['readyForSupervisedClose'])
 def test_order_not_filled(self):self.assertFalse(self.runcheck(entry={**E,'status':'NEW'})['readyForSupervisedClose'])
 def test_no_send_any_branch(self):
  for kw in ({},{'conditional':[]},{'positions':[]},{'account_read_complete':False}):
   r=self.runcheck(**kw)
   self.assertIs(r['maySendOrder'],False);self.assertEqual(r['exchangeWrites'],0)
if __name__=='__main__':unittest.main()
