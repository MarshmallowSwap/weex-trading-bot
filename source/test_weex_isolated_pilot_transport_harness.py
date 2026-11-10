"""Network-free simulated transport tests including ambiguous responses and restarts."""
import tempfile,unittest
from pathlib import Path
from weex_isolated_pilot_offline_journal import reserve
from weex_isolated_pilot_transport_harness import simulate_dispatch
class MockGateway:
 simulation_only=True
 def __init__(self,result=None,raise_error=False):
  self.calls=0;self.result=result or {'success':True,'orderId':'SIM-1'}
  self.raise_error=raise_error
 def simulate(self,operation,payload):
  self.calls+=1
  if self.raise_error:raise TimeoutError('simulated uncertainty')
  return self.result
class PilotTransportTest(unittest.TestCase):
 def prepared(self,db):
  reserve(db,pilot_id='abc',side='LONG',quantity='0.002',stop_price='2100')
 def test_simulated_ack_not_live_approval(self):
  with tempfile.TemporaryDirectory() as folder:
   db=Path(folder)/'mock.sqlite3';self.prepared(db)
   g=MockGateway()
   out=simulate_dispatch(db,'abc','entry',g)
   self.assertEqual(out['state'],'SIMULATED_ACK_ONLY')
   self.assertFalse(out['exchangeAccepted'])
   self.assertFalse(out['nextStageAuthorized'])
   self.assertEqual(g.calls,1)
 def test_duplicate_after_restart_no_resend(self):
  with tempfile.TemporaryDirectory() as folder:
   db=Path(folder)/'mock.sqlite3';self.prepared(db);g=MockGateway()
   simulate_dispatch(db,'abc','entry',g)
   second=simulate_dispatch(db,'abc','entry',g)
   self.assertEqual(second['state'],'ALREADY_HANDLED_NO_RETRY')
   self.assertEqual(g.calls,1)
 def test_timeout_stays_unknown_and_never_retries(self):
  with tempfile.TemporaryDirectory() as folder:
   db=Path(folder)/'mock.sqlite3';self.prepared(db);g=MockGateway(raise_error=True)
   outcome=simulate_dispatch(db,'abc','entry',g)
   self.assertEqual(outcome['state'],'SIMULATION_OUTCOME_UNKNOWN')
   self.assertFalse(outcome['retryAllowed'])
   simulate_dispatch(db,'abc','entry',g)
   self.assertEqual(g.calls,1)
 def test_real_gateway_rejected(self):
  with tempfile.TemporaryDirectory() as folder:
   db=Path(folder)/'mock.sqlite3';self.prepared(db)
   with self.assertRaises(PermissionError):
    simulate_dispatch(db,'abc','entry',object())
 def test_stop_and_close_require_verified_external_state(self):
  with tempfile.TemporaryDirectory() as folder:
   db=Path(folder)/'mock.sqlite3';self.prepared(db);g=MockGateway()
   for stage in ('stop','close'):
    self.assertEqual(simulate_dispatch(db,'abc',stage,g)['state'],'PREREQUISITE_NOT_CERTIFIED')
   self.assertEqual(g.calls,0)
if __name__=='__main__':unittest.main()
