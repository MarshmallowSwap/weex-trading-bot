import tempfile,unittest
from pathlib import Path
from weex_live_manual_attestation import establish
from weex_live_manual_isolation_policy import assess
def pos(symbol,id,quantity):
 return {'symbol':symbol,'side':'SHORT','id':id,'size':quantity,
         'openValue':'1','cumOpenSize':'1','cumOpenValue':'1',
         'createdTime':1,'createdMatchSequenceId':1}
class Isolation(unittest.TestCase):
 def setUp(self):
  td=tempfile.TemporaryDirectory();self.addCleanup(td.cleanup);self.root=Path(td.name)
  self.positions=[pos('TRUTHUSDT',1,'10'),pos('UAIUSDT',2,'20')]
  establish(self.root,self.positions,user_attested=True)
 def check(self,positions=None,orders=None,algos=None,margin='cross'):
  return assess(self.root,self.positions if positions is None else positions,
       [] if orders is None else orders,[] if algos is None else algos,
       margin_preference=margin)
 def test_exact_manual_position_excluded(self):
  r=self.check()
  self.assertEqual(r['manualSymbols'],['TRUTHUSDT','UAIUSDT'])
  self.assertFalse(r['canTouchManualPosition'])
  self.assertFalse(r['canTouchManualOrders'])
 def test_cross_exposure_never_isolated(self):
  r=self.check()
  self.assertIn('CROSS_MARGIN_SHARES_COLLATERAL',r['reasons'])
  self.assertFalse(r['physicalCollateralIsolation'])
  self.assertFalse(r['canOpenBotTrade'])
 def test_isolated_preference_not_exchange_proof(self):
  r=self.check(margin='isolated')
  self.assertFalse(r['physicalCollateralIsolation'])
  self.assertFalse(r['canOpenBotTrade'])
 def test_position_changed_requires_review(self):
  changed=[{**self.positions[0],'size':'11'},self.positions[1]]
  self.assertEqual(self.check(positions=changed)['state'],'REVIEW_REQUIRED')
 def test_unexpected_position_requires_review(self):
  more=self.positions+[pos('BTCUSDT',4,'1')]
  self.assertFalse(self.check(positions=more)['canOpenBotTrade'])
  self.assertIn('POSITION_IDENTITY_CHANGED_OR_NOT_ATTESTED',
                self.check(positions=more)['reasons'])
 def test_manual_algo_never_adopted(self):
  r=self.check(algos=[{'symbol':'TRUTHUSDT','algoId':123}])
  self.assertFalse(r['canTouchManualOrders'])
  self.assertEqual(r['manualPositions'],2)
 def test_other_algo_detected(self):
  r=self.check(algos=[{'symbol':'BTCUSDT','algoId':456}])
  self.assertIn('NON_MANUAL_ORDER_PRESENT_REQUIRES_RECONCILIATION',r['reasons'])
 def test_invalid_snapshot(self):
  self.assertEqual(self.check(positions=[None])['state'],'INVALID_ACCOUNT_SNAPSHOT')
if __name__=='__main__':unittest.main()
