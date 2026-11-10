import unittest,copy
from weex_release_candidate_20261109 import grade
G={'gate':'NO_GO','passed':8,'total':10,'checks':{'historical_quote_amounts_reconciled':False,'crash_restart_recovery_live_tested':False}}
C={'execution':{'enabled':False,'mode':'PRETRADE'}}
P={'livePilotCycleCertified':True,'livePilotAttachedStopCertified':True,
   'livePilotReduceOnlyExitCertified':True,'positionsAndPendingOrdersZero':True}
L={'boundedLedgerAccountingCertified':True,'ledgerWindowComplete':True,
   'balanceArithmetic':{'gaps':[],'transitionsChecked':1334},
   'entireAccountLifetimeCertified':False}
X={'allSimulatedWriteBoundaryChecksPassed':True,'newProductionWrites':0,
   'realExchangeWriteActuallyInterrupted':False}
class Release(unittest.TestCase):
 def inspect(self,**kw):
  a=dict(gate=G,config=C,mode='STOPPED',integrity=[],pilot=P,ledger=L,
         crash=X,account=([],[],[]));a.update(kw);return grade(**a)
 def test_candidate_yes_auto_no(self):
  r=self.inspect();self.assertTrue(r['candidatePrepared'])
  self.assertFalse(r['globalTradingAuthorized'])
  self.assertEqual(r['executionWrites'],0)
 def test_unverified_crash_not_auto_go_even_gate_claims_go(self):
  g={'gate':'GO','passed':10,'total':10,'checks':{k:True for k in G['checks']}}
  self.assertFalse(self.inspect(gate=g)['globalTradingAuthorized'])
 def test_account_position_blocks(self):
  self.assertFalse(self.inspect(account=([{'symbol':'ETHUSDT'}],[],[]))['candidatePrepared'])
 def test_running_switch_blocks(self):
  self.assertFalse(self.inspect(mode='RUNNING')['candidatePrepared'])
 def test_missing_ledger_proof_blocks(self):
  self.assertFalse(self.inspect(ledger={})['candidatePrepared'])
 def test_missing_pilot_proof_blocks(self):
  self.assertFalse(self.inspect(pilot={})['candidatePrepared'])
 def test_code_integrity_failed_blocks(self):
  self.assertFalse(self.inspect(integrity=['MANIFEST_ERROR'])['candidatePrepared'])
if __name__=='__main__':unittest.main()
