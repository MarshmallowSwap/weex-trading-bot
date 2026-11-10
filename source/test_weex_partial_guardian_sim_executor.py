import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from weex_partial_guardian_persistent import register,STEPS
from weex_partial_guardian_sim_executor import execute_one
from test_weex_partial_guardian_replay import B,POS,OTP,OSL,NSL,NTP,STAGES
from weex_partial_guardian_sim_transport import UncertainWrite
class SimExecutorTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.db=str(Path(self.tmp.name)/'journal.sqlite')
  # Real production runner has additional canary client-ID check.
  bind={**B,'new_tp_client':'wxsimpnew','new_sl_client':'wxsimslnew'}
  register(self.db,'t',**bind)
  self.algos=[
   {**OTP},{**OSL}]
  self.writes=0
 def snap(self,transport=None):
  return {'positions':POS,'algos':[dict(a) for a in self.algos],
          'regular_orders':[],'complete':True}
 def dispatch(self,step,spec,transport=None):
  self.writes+=1
  if step==STEPS[0]:
   self.algos.append({**NSL,'clientAlgoId':'wxsimslnew'})
  elif step==STEPS[1]:
   self.algos=[x for x in self.algos if x['clientAlgoId']!='oldsl']
  elif step==STEPS[2]:
   self.algos=[x for x in self.algos if x['clientAlgoId']!='oldtp']
  elif step==STEPS[3]:
   self.algos.append({**NTP,'clientAlgoId':'wxsimpnew'})
  return {'status':'ACK_RECEIVED_READBACK_REQUIRED'}
 def run_one(self):
  with patch('weex_partial_guardian_sim_executor.snapshot',side_effect=self.snap):
   with patch('weex_partial_guardian_sim_executor.send_sim_only',side_effect=self.dispatch):
    return execute_one(self.db,'t',new_stop_trigger='80000',new_tp_limit='120000')
 def test_four_steps_exactly_once(self):
  expected=['DUPLICATE_STOPS_REVIEW','NEW_STOP_ONLY_OLD_TP_REVIEW',
    'NEW_STOP_PRESENT_TP_MISSING','PAIR_RESTORED_OFFLINE_ONLY']
  for target in expected:
   r=self.run_one()
   self.assertEqual(r['state'],target)
   self.assertTrue(r['confirmedByReadback'])
  self.assertEqual(self.writes,4)
  self.assertFalse(self.run_one()['stepSent'])
  self.assertEqual(self.writes,4)
 def test_timeout_durable_block(self):
  def uncertain(step,spec,transport=None):
   self.writes+=1
   raise UncertainWrite('ACK_UNKNOWN')
  with patch('weex_partial_guardian_sim_executor.snapshot',side_effect=self.snap):
   with patch('weex_partial_guardian_sim_executor.send_sim_only',side_effect=uncertain):
    first=execute_one(self.db,'t',new_stop_trigger='80000',new_tp_limit='120000')
    self.assertEqual(first['state'],'ACK_UNCERTAIN')
  next_attempt=self.run_one()
  self.assertEqual(next_attempt['reason'],'PENDING_OUTCOME_REQUIRES_READBACK')
  self.assertEqual(self.writes,1)
 def test_cannot_trade_without_position(self):
  with patch('weex_partial_guardian_sim_executor.snapshot',
             return_value={'positions':[],'algos':[],'regular_orders':[],'complete':True}):
   result=execute_one(self.db,'t',new_stop_trigger='80000',new_tp_limit='120000')
   self.assertFalse(result['stepSent'])
 def test_cannot_trade_different_symbol(self):
  db=str(Path(self.tmp.name)/'different.sqlite')
  register(db,'x',**{**B,'symbol':'ETHUSDT'})
  result=execute_one(db,'x',new_stop_trigger='80000',new_tp_limit='120000')
  self.assertEqual(result['reason'],'DEMO_CANARY_SYMBOL_SIDE_ONLY')
 def test_missing_old_id_does_not_cancel_anything(self):
  self.algos=[OSL,NSL]
  with patch('weex_partial_guardian_sim_executor.snapshot',side_effect=self.snap):
   result=execute_one(self.db,'t',new_stop_trigger='80000',new_tp_limit='120000')
  self.assertFalse(result['stepSent'])
if __name__=='__main__':unittest.main()
