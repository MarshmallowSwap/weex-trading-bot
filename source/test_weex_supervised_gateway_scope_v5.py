"""Proof that supervised V5 pilot plan matches the existing production gateway scope.
This test performs no exchange reads/writes.
"""
import ast,unittest,tempfile
from pathlib import Path
from weex_live_worker import SCOPE
ROOT=Path(__file__).resolve().parent
class SupervisedGatewayContract(unittest.TestCase):
 def test_worker_scope_is_bound_in_pilot_plan(self):
  program=ast.parse((ROOT/'weex_supervised_crash_entry_child_v5.py').read_text(encoding='utf-8'))
  updates=[n for n in ast.walk(program) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)
           and n.func.attr=='update' and isinstance(n.func.value,ast.Name) and n.func.value.id=='plan']
  matched=[kw for call in updates for kw in call.keywords if kw.arg=='liveAuthorizationScope']
  self.assertEqual(len(matched),1)
  self.assertIsInstance(matched[0].value,ast.Name)
  self.assertEqual(matched[0].value.id,'SCOPE')
  self.assertEqual(SCOPE,'USER_ACTIVATED_LIVE_V1')
 def test_no_hardcoded_permit_approval(self):
  program=ast.parse((ROOT/'weex_supervised_crash_entry_child_v5.py').read_text(encoding='utf-8'))
  for n in ast.walk(program):
   if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='authorize_once':
    decisions=[kw.value for kw in n.keywords if kw.arg=='approval']
    self.assertEqual(len(decisions),1)
    self.assertIsInstance(decisions[0],ast.Name)
    self.assertEqual(decisions[0].id,'decision')
 def test_native_windows_supervisor_pid_check(self):
  from weex_supervised_crash_entry_child_v5 import process_alive,supervisor_ready
  import os
  self.assertFalse(process_alive(os.getpid()))
  self.assertFalse(process_alive(99999999))
  with tempfile.TemporaryDirectory() as td:
   self.assertFalse(supervisor_ready(td))
if __name__=='__main__':unittest.main()
