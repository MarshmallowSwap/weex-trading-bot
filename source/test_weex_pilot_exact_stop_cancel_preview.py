import unittest
from weex_pilot_exact_stop_cancel_preview import exact_plan,preview_sdk,verify_cancel
P={'symbol':'ETHUSDT','id':'123','side':'LONG','size':'0.002','marginType':'ISOLATED'}
S={'algoId':'123456789','symbol':'ETHUSDT','positionSide':'LONG','side':'SELL',
   'orderType':'STOP_MARKET','algoStatus':'UNTRIGGERED','reduceOnly':True,
   'closePosition':True,'quantity':'0','triggerPrice':'2110'}
class ExactCancel(unittest.TestCase):
 def test_sdk_captures_single_exact_id_and_zero_network(self):
  self.assertEqual(preview_sdk('123456789')['networkRequests'],0)
 def test_scoped_plan_never_grants_send(self):
  r=exact_plan(pilot_stop=S,observed=S,position=P,approved_id='123456789')
  self.assertTrue(r['prepared']);self.assertFalse(r['canSend'])
 def test_unrelated_order_rejected(self):
  r=exact_plan(pilot_stop=S,observed={**S,'algoId':'123456788'},position=P,
               approved_id='123456789')
  self.assertFalse(r['prepared'])
 def test_wrong_approval_rejected(self):
  r=exact_plan(pilot_stop=S,observed=S,position=P,approved_id='123456788')
  self.assertFalse(r['prepared'])
 def test_cancel_ack_is_not_terminal_proof(self):
  r=verify_cancel(order_id='123456789',history_order={**S,'algoStatus':'UNTRIGGERED'},
                  open_orders=[],positions=[P])
  self.assertFalse(r['verified'])
 def test_exact_terminal_without_open_order(self):
  r=verify_cancel(order_id='123456789',history_order={**S,'algoStatus':'CANCELED'},
                  open_orders=[],positions=[P])
  self.assertTrue(r['verified']);self.assertFalse(r['canClose'])
 def test_other_conditional_blocks(self):
  r=verify_cancel(order_id='123456789',history_order={**S,'algoStatus':'CANCELED'},
                  open_orders=[{**S,'algoId':'987654321'}],positions=[P])
  self.assertFalse(r['verified'])
if __name__=='__main__':unittest.main()
