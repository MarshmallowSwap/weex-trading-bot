import unittest
from weex_pilot_ownership_attestation import attest
B={'account':'CURRENT_WEEX','snapshotVerified':True,'observedAtMs':1000,
   'positions':[],'regularOrders':[],'conditionalOrders':[]}
P={'entryId':'wxpilot_1','quantity':'0.002','side':'LONG'}
O={'clientOrderId':'wxpilot_1','orderId':'e1','time':1100,
   'status':'FILLED','symbol':'ETHUSDT','positionSide':'LONG',
   'side':'BUY','executedQty':'0.002'}
X={'id':'990','createdTime':1200,'symbol':'ETHUSDT',
   'side':'LONG','marginType':'ISOLATED','size':'0.002'}
F=[{'id':'f1','orderId':'e1','symbol':'ETHUSDT','side':'BUY',
    'positionSide':'LONG','qty':'0.002','time':1250}]
def run(b=B,p=P,o=O,x=X,f=F):
 return attest(baseline=b,position=x,entry=o,fill_rows=f,pilot=p)
class PilotOwnership(unittest.TestCase):
 def test_exact_attestation(self):
  r=run();self.assertTrue(r['owned'],r);self.assertEqual(r['positionId'],'990')
 def test_baseline_with_position_blocks(self):
  self.assertFalse(run(b={**B,'positions':[X]})['owned'])
 def test_baseline_unknown_blocks(self):
  self.assertFalse(run(b={**B,'snapshotVerified':False})['owned'])
 def test_wrong_client_blocks(self):
  self.assertFalse(run(o={**O,'clientOrderId':'manual'})['owned'])
 def test_order_before_baseline_blocks(self):
  self.assertFalse(run(o={**O,'time':999})['owned'])
 def test_cross_blocks(self):
  self.assertFalse(run(x={**X,'marginType':'CROSSED'})['owned'])
 def test_other_position_qty_blocks(self):
  self.assertFalse(run(x={**X,'size':'0.004'})['owned'])
 def test_duplicate_fill_blocks(self):
  self.assertFalse(run(f=F+F)['owned'])
 def test_unbound_fill_blocks(self):
  self.assertFalse(run(f=[{**F[0],'orderId':'other'}])['owned'])
 def test_no_fills_blocks(self):
  self.assertFalse(run(f=[])['owned'])
if __name__=='__main__':unittest.main()
