import unittest
from weex_pilot_isolated_close_plan import plan
P={'side':'LONG','quantity':'0.002','entryId':'pilot-entry','closeId':'pilot-close'}
O={'clientOrderId':'pilot-entry','orderId':'EX-1','status':'FILLED','symbol':'ETHUSDT','positionSide':'LONG','side':'BUY'}
F=[{'id':'f-1','orderId':'EX-1','qty':'0.002','symbol':'ETHUSDT','positionSide':'LONG','side':'BUY'}]
POS=[{'symbol':'ETHUSDT','side':'LONG','size':'0.002','marginType':'ISOLATED','manualOrMixed':False}]
def check(p=P,o=O,f=F,pos=POS,reg=None,alg=None,fresh=True):
 return plan(pilot=p,entry_order=o,entry_fills=f,positions=pos,
             regular_orders=[] if reg is None else reg,algos=[] if alg is None else alg,
             observed_fresh=fresh)
class ExactIsolatedClose(unittest.TestCase):
 def test_exact_verified_entry_prepares_unsigned_close(self):
  r=check();self.assertTrue(r['prepared'])
  self.assertFalse(r['canSend']);self.assertEqual(r['exchangeWrites'],0)
  self.assertTrue(r['payload']['reduceOnly'])
  self.assertEqual(r['payload']['newClientOrderId'],'pilot-close')
 def test_manual_or_mixed_blocks(self):
  self.assertFalse(check(pos=[{**POS[0],'manualOrMixed':True}])['prepared'])
 def test_cross_blocks(self):
  self.assertFalse(check(pos=[{**POS[0],'marginType':'CROSS'}])['prepared'])
 def test_extra_position_blocks(self):
  self.assertFalse(check(pos=POS+POS)['prepared'])
 def test_order_conflict_blocks(self):
  self.assertFalse(check(reg=[{'symbol':'ETHUSDT'}])['prepared'])
 def test_stale_blocks(self):
  self.assertFalse(check(fresh=False)['prepared'])
 def test_wrong_entry_identity_blocks(self):
  self.assertFalse(check(o={**O,'clientOrderId':'other'})['prepared'])
 def test_duplicate_fill_blocks(self):
  self.assertFalse(check(f=F+F)['prepared'])
 def test_partial_fill_blocks(self):
  self.assertFalse(check(f=[{**F[0],'qty':'0.001'}])['prepared'])
if __name__=='__main__':unittest.main()
