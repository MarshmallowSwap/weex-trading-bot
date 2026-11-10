import unittest
from datetime import datetime,timezone
from weex_live_guardian_shadow_gate import evaluate
NOW=datetime(2026,11,5,1,0,tzinfo=timezone.utc).timestamp()
STAMP=datetime.fromtimestamp(NOW,timezone.utc).isoformat()
C={'execution':{'enabled':False,'allowOrdersWithoutStop':False},
   'risk':{'stopLoss':{'enabled':True},'marginModePreference':'isolated'},
   'strategySettings':{'slMode':'percent'}}
W={'status':'WAIT_SIGNAL_OR_GATES','recoveryClear':True}
R={'checkedAt':STAMP,'writes':False,'liveGo':False}
L={'gate':'GO','checkedAt':STAMP}
def check(c=None,mode='STOPPED',worker=None,recon=None,release=None,
          positions=None,algos=None,ownership=True):
 return evaluate(C if c is None else c,mode,W if worker is None else worker,
                 R if recon is None else recon,L if release is None else release,
                 current_positions=[] if positions is None else positions,
                 current_open_algos=[] if algos is None else algos,
                 positions_bound_to_bot=ownership,now=NOW)
class TestGate(unittest.TestCase):
 def test_clean_preflight_still_cannot_authorize_live(self):
  x=check();self.assertEqual(x['state'],'PREFLIGHT_ONLY_NO_TRADE_AUTHORIZATION')
  self.assertFalse(x['newEntriesPermitted'])
 def test_stop_loss_disabled(self):
  x=check(c={**C,'risk':{'stopLoss':{'enabled':False},'marginModePreference':'isolated'}})
  self.assertIn('INCONSISTENT_OPTIONAL_SL_SETTINGS',x['checks'])
 def test_sl_mode_off(self):
  x=check(c={**C,'strategySettings':{'slMode':'off'}})
  self.assertIn('INCONSISTENT_OPTIONAL_SL_SETTINGS',x['checks'])
 def test_allow_no_stop(self):
  x=check(c={**C,'execution':{'enabled':False,'allowOrdersWithoutStop':True}})
  self.assertIn('INCONSISTENT_OPTIONAL_SL_SETTINGS',x['checks'])
 def test_shared_collateral(self):
  x=check(c={**C,'risk':{'stopLoss':{'enabled':True},'marginModePreference':'cross'}})
  self.assertIn('CROSS_MARGIN_SHARED_COLLATERAL_RISK',x['checks'])
 def test_unattributed_position_blocks(self):
  x=check(positions=[{'symbol':'BTCUSDT'}],ownership=False)
  self.assertIn('EXISTING_POSITIONS_NOT_BOT_ATTRIBUTED',x['checks'])
 def test_release_stale(self):
  x=check(release={'gate':'GO','checkedAt':'2025-01-01T00:00:00+00:00'})
  self.assertIn('RELEASE_GATE_STALE',x['checks'])
 def test_unclear_recovery(self):
  x=check(worker={'status':'BLOCKED_RECOVERY','recoveryClear':False})
  self.assertIn('WORKER_HAS_UNRESOLVED_RECOVERY',x['checks'])
 def test_no_snapshot(self):
  x=evaluate(C,'STOPPED',W,R,L,now=NOW)
  self.assertIn('CURRENT_POSITIONS_NOT_VERIFIED',x['checks'])
 def test_running_during_preflight(self):
  self.assertIn('LIVE_SWITCH_NOT_STOPPED_DURING_PREFLIGHT',check(mode='RUNNING')['checks'])
if __name__=='__main__':unittest.main()
