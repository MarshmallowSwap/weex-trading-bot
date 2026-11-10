"""Offline end-to-end safety contract across monitor, exit and CROSS guardian.

Real modules, isolated local SQLite, dummy incident proofs. No WEEX calls,
no operator grants on production, no live readiness claims.
"""
import json,os,subprocess,sys,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
from weex_supervised_process_monitor_v6 import tick
from weex_supervised_crash_entry_child_v5 import supervisor_ready
from weex_supervised_exit_policy_v7 import grant,consume,status
from weex_supervised_crash_executor_v2 import CLIENT_ID
from weex_supervisor_promotion_policy_v16 import assess

P={'symbol':'ETHUSDT','side':'SELL','positionSide':'LONG','type':'MARKET',
   'quantity':'0.001','newClientOrderId':'wxclose_'+CLIENT_ID.split('_',1)[1],
   'reduceOnly':True}
E={'status':'VERIFIED_PROTECTED_NEED_EXACT_CLOSE','clientOrderId':CLIENT_ID,
   'symbol':'ETHUSDT','quantity':'0.001','positionId':'123','stopAlgoId':'456'}
CAP={'taskS4UVerified':True,'supervisorHeartbeatLive':True,
     'productionIntegrityPass':True,'reduceOnlySdkPreviewPass':True,
     'apiHeadroomReady':True,'exitPermitActive':True}
def flat():
 t=time.time()
 return {'complete':True,'startedAtMs':int((t-1)*1000),
   'completedAtMs':int((t-.5)*1000),'positions':[],
   'regularOrders':[],'conditionalOrders':[],'trailingOrders':[]}
def synthetic(root):
 return {'status':'VERIFIED_PROTECTED_REQUIRES_EXTERNAL_CLOSE_APPROVAL'}
def plan(root):
 return {'status':'EXACT_CLOSE_PROPOSAL_REQUIRES_SEPARATE_AUTHORIZATION'}

class Integration(unittest.TestCase):
 def test_supervisor_os_process_heartbeat_never_claims_ready(self):
  with tempfile.TemporaryDirectory() as d:
   script=("import json,sys; from weex_supervised_process_monitor_v6 import run;"
     " out=run(sys.argv[1],iterations=2,interval=.15,heartbeat_interval=.1,"
     "observer=lambda root:{'status':'NO_PENDING_CRASH_INTENT'});"
     " print(json.dumps(out))")
   child=subprocess.run([sys.executable,'-B','-c',script,d],cwd=str(Path(__file__).parent),
                        capture_output=True,text=True,timeout=10)
   self.assertEqual(child.returncode,0,child.stderr)
   payload=json.loads(child.stdout.strip())
   self.assertEqual(payload['iterations'],2)
   h=json.loads((Path(d)/'weex_supervised_crash_supervisor_health.json').read_text())
   self.assertEqual(h['status'],'OBSERVING_NOT_ARMED')
   self.assertFalse(h['entryDispatchAllowed'])
   self.assertFalse(h['closeDispatchAllowed'])
   self.assertFalse(supervisor_ready(d))
 def test_exit_only_permit_is_durable_consumed_once(self):
  with tempfile.TemporaryDirectory() as d:
   with patch('live_control.state',return_value={'mode':'STOPPED'}),patch('live_control.build_errors',return_value=[]):
    self.assertEqual(grant(d,operator_authorized=True)['status'],'EXIT_ONLY_POLICY_GRANTED')
   self.assertTrue(status(d)['canClose'])
   self.assertFalse(consume(d,'post_capi_v3_order',dict(P,reduceOnly=False),E))
   self.assertTrue(consume(d,'post_capi_v3_order',P,E))
   self.assertFalse(consume(d,'post_capi_v3_order',P,E))
   self.assertFalse(status(d)['canClose'])
 def test_real_monitor_no_exit_without_independent_permit(self):
  with tempfile.TemporaryDirectory() as d:
   invoked=[]
   result=tick(d,observer=synthetic,recovery_planner=plan,
      worker_recovery=lambda root:{'status':'RESTART_READBACK_UNVERIFIED','workerRestartConfirmed':False},
      exit_policy_reader=lambda root:{'canClose':False},
      exit_executor=lambda root:invoked.append('EXECUTED'))
   self.assertEqual(invoked,[])
   self.assertEqual(result['exitPolicyResult'],'NOT_AUTHORIZED')
   self.assertFalse(result['releaseCertified'])
 def test_manual_cross_blocks_promotion_even_with_fake_permit(self):
  s=flat()
  s['positions']=[{'symbol':'AINUSDT','id':'999','side':'SHORT','size':'100'}]
  s['conditionalOrders']=[{'symbol':'AINUSDT','algoId':'888'}]
  a=assess(CAP,s)
  self.assertIn('SHARED_CROSS_COLLATERAL_NOT_FLAT',a['blockers'])
  self.assertFalse(a['entryAuthorized'])
  self.assertFalse(a['heartbeatPromotionAllowed'])
 def test_flat_account_is_not_enough_to_claim_operational_promotion(self):
  a=assess(CAP,flat())
  self.assertIn('VERIFIED_OPERATIONAL_PROMOTION_CONTROLLER_NOT_INSTALLED',a['blockers'])
  self.assertFalse(a['heartbeatPromotionAllowed'])

if __name__=='__main__':unittest.main()
