import unittest,copy
from weex_pilot_independent_preflight import assess
P={'exchange':'WEEX','marginMode':'ISOLATED','leverage':1,'maxNewOrders':1,
   'executionEnabled':False,'liveOrderSubmissionAllowed':False,
   'stopLossVerified':False,'reduceOnlyCloseVerified':False}
OBS={'issues':['INDEPENDENT_GATE_NO_GO','LIVE_CRASH_RESTART_NOT_CERTIFIED',
               'PILOT_STOP_LOSS_NOT_VERIFIED','REDUCE_ONLY_EXIT_NOT_VERIFIED'],
     'indicativeOrder':{'quantity':'0.002','quantityStep':'0.001','notionalUSDT':'4.48'}}
J={'state':'READ_ONLY','records':0,'dispatchRows':0}
def check(p=None,o=None,j=None,mode='STOPPED',errors=None):
 return assess(P if p is None else p,OBS if o is None else o,J if j is None else j,
               main_switch=mode,integrity_errors=[] if errors is None else errors)
class IndependentPilot(unittest.TestCase):
 def test_production_no_go_not_pilot_specific_reason(self):
  r=check()
  self.assertNotIn('INDEPENDENT_GATE_NO_GO',r['issues'])
  self.assertNotIn('LIVE_CRASH_RESTART_NOT_CERTIFIED',r['issues'])
  self.assertNotIn('EMERGENCY_CLOSE_NOT_ATTESTED',r['issues'])
  self.assertTrue(r['pilotPreparationReady'])
  self.assertIn('EMERGENCY_CLOSE_NOT_ATTESTED',r['liveExecutionBlockers'])
  self.assertFalse(r['pilotLiveExecutionReady'])
  self.assertFalse(r['pilotOrderAuthorized'])
 def test_main_switch_must_be_stopped(self):
  self.assertIn('MAIN_BOT_NOT_STOPPED',check(mode='RUNNING')['issues'])
 def test_integrity_failure(self):
  self.assertIn('CODE_INTEGRITY_FAILED',check(errors=['MANIFEST_INCOMPLETO'])['issues'])
 def test_exposure_blocker_preserved(self):
  o=copy.deepcopy(OBS);o['issues'].append('EXISTING_EXPOSURE_OR_INCOMPLETE')
  self.assertIn('EXISTING_EXPOSURE_OR_INCOMPLETE',check(o=o)['issues'])
 def test_journal_not_empty(self):
  j={**J,'records':1}
  self.assertIn('PILOT_JOURNAL_NOT_PRISTINE',check(j=j)['issues'])
 def test_size_above_five(self):
  o=copy.deepcopy(OBS);o['indicativeOrder']['notionalUSDT']='5.001'
  self.assertIn('PILOT_ORDER_SIZE_NOT_CERTIFIED',check(o=o)['issues'])
 def test_unverified_close_never_authorizes_real_order(self):
  p={**P,'reduceOnlyCloseVerified':True}
  o=copy.deepcopy(OBS);o['issues'].remove('REDUCE_ONLY_EXIT_NOT_VERIFIED')
  r=check(p=p,o=o)
  self.assertTrue(r['pilotPreparationReady'],r['issues'])
  self.assertFalse(r['pilotOrderAuthorized'])
 def test_relevant_stop_optional(self):
  self.assertNotIn('PILOT_STOP_LOSS_NOT_VERIFIED',check()['issues'])
if __name__=='__main__':unittest.main()
