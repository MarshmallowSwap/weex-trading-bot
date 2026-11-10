import unittest
from weex_finalize_two_historical_closes import certified
Q={'state':'HISTORICAL_BOT_TP_PROOF_REVALIDATED','symbol':'QNTUSDT',
   'targetMetBeforeFunding':False,'proofSha256':'abc'}
L={'status':'EXTERNAL_TP_HISTORICAL_CLOSE_VERIFIED','symbol':'LTCUSDT',
   'botTPUsed':False,'stillNotBotTP':True,'flatAccountConfirmed':True,
   'evidenceSha256':'def','targetMetBeforeFunding':False}
class CloseProofGate(unittest.TestCase):
 def test_verified_evidence_accepted_for_precommit(self):
  self.assertTrue(certified(Q,L))
 def test_bot_tp_must_not_be_external(self):
  with self.assertRaises(ValueError):certified(Q,{**L,'botTPUsed':True})
 def test_ltc_must_be_flat(self):
  with self.assertRaises(ValueError):certified(Q,{**L,'flatAccountConfirmed':False})
 def test_qnt_requires_digest(self):
  with self.assertRaises(ValueError):certified({**Q,'proofSha256':''},L)
 def test_wrong_symbol_rejected(self):
  with self.assertRaises(ValueError):certified({**Q,'symbol':'BTCUSDT'},L)
 def test_unverified_external_refused(self):
  with self.assertRaises(ValueError):certified(Q,{**L,'status':'NOT_VERIFIED'})
 def test_target_not_claimed_met(self):
  with self.assertRaises(ValueError):certified({**Q,'targetMetBeforeFunding':True},L)
if __name__=='__main__':unittest.main()
