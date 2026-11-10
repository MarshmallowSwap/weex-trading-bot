"""V5 entry permission remains disabled without externally wired proof."""
import sys,unittest
from unittest.mock import patch
from weex_supervised_crash_entry_child_v5 import run_child
class EntryFailClosed(unittest.TestCase):
 def test_direct_execution_rejected(self):
  with self.assertRaisesRegex(PermissionError,'ACTUAL_WORKER_PROCESS_REQUIRED'):
   run_child()
 def test_worker_without_external_authority_rejected_before_exchange(self):
  with patch.object(sys,'argv',['weex_live_worker.py','--supervised-crash-child']):
   with patch('weex_supervised_crash_entry_child_v5.fresh_capture',side_effect=AssertionError('ACCOUNT_CAPTURE_NOT_ALLOWED')):
    with self.assertRaisesRegex(PermissionError,'INDEPENDENT_EXACT_APPROVAL_AND_EVIDENCE_REQUIRED'):
     run_child()
 def test_one_callback_is_not_enough(self):
  with patch.object(sys,'argv',['weex_live_worker.py','--supervised-crash-child']):
   with patch('weex_supervised_crash_entry_child_v5.fresh_capture',side_effect=AssertionError('ACCOUNT_CAPTURE_NOT_ALLOWED')):
    with self.assertRaisesRegex(PermissionError,'INDEPENDENT_EXACT_APPROVAL_AND_EVIDENCE_REQUIRED'):
     run_child(external_approval=lambda *args:True)
if __name__=='__main__':unittest.main()
