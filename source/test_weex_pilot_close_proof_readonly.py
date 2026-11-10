import unittest
from weex_pilot_close_proof_readonly import verify_close
O={'clientOrderId':'pilot-close','orderId':'EX-1','symbol':'ETHUSDT',
   'positionSide':'LONG','side':'SELL','reduceOnly':True,
   'status':'FILLED','origQty':'0.002','executedQty':'0.002'}
F=[{'id':'fill1','orderId':'EX-1','symbol':'ETHUSDT','positionSide':'LONG',
    'side':'SELL','qty':'0.001'},
   {'id':'fill2','orderId':'EX-1','symbol':'ETHUSDT','positionSide':'LONG',
    'side':'SELL','qty':'0.001'}]
def check(orders=None,fills=None,positions=None):
 return verify_close(client_id='pilot-close',side='LONG',quantity='0.002',
                     orders=[O] if orders is None else orders,
                     fills=F if fills is None else fills,
                     positions=[] if positions is None else positions)
class ReadonlyProofTest(unittest.TestCase):
 def test_consistent_does_not_grant_live_approval(self):
  x=check()
  self.assertEqual(x['state'],'CONSISTENT_OBSERVATIONS_UNATTESTED')
  self.assertFalse(x['closeCertifiedForLive'])
 def test_missing_fills(self):
  self.assertEqual(check(fills=[])['reason'],'FILLS_NOT_AVAILABLE')
 def test_partial_fills(self):
  self.assertEqual(check(fills=F[:1])['reason'],'INCOMPLETE_FILLS')
 def test_position_remains(self):
  self.assertEqual(check(positions=[{'symbol':'ETHUSDT','positionSide':'LONG','size':'0.001'}])['reason'],'POSITION_STILL_OPEN')
 def test_duplicate_fill(self):
  self.assertEqual(check(fills=F+[F[0]])['reason'],'DUPLICATE_OR_MISSING_FILL_ID')
 def test_wrong_side(self):
  self.assertEqual(check(orders=[{**O,'side':'BUY'}])['reason'],'CLOSE_ORDER_NOT_EXACT')
 def test_wrong_client(self):
  self.assertEqual(check(orders=[{**O,'clientOrderId':'manual'}])['reason'],'MISSING_OR_AMBIGUOUS_EXIT')
 def test_no_reduce_only(self):
  self.assertEqual(check(orders=[{**O,'reduceOnly':False}])['reason'],'CLOSE_ORDER_NOT_EXACT')
 def test_duplicate_order(self):
  self.assertEqual(check(orders=[O,O])['reason'],'MISSING_OR_AMBIGUOUS_EXIT')
if __name__=='__main__':unittest.main()
