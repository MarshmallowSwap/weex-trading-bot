"""Independent veto tests for recovery integration. No exchange network."""
import unittest,copy
from unittest.mock import patch
from weex_worker_recovery_readonly_20261109 import worker_uncertain_entry_guard
from test_weex_worker_recovery_readonly_20261109 import T,W,O,P,A
class FakeReader:
 def __init__(self,positions=None,algos=None):
  self.positions=[P] if positions is None else positions
  self.algos=[A] if algos is None else algos
  self.calls=0
 def read(self,*args,**kwargs):
  raise AssertionError('PAGED_READ_MUST_BE_MOCKED')
 def account(self):
  self.calls+=1
  return self.positions,[],self.algos
class WorkerIntegratedRecovery(unittest.TestCase):
 def item(self,state='REVIEW_REQUIRED',write='UNKNOWN'):
  t={**T,'state':state,'created':1}
  w={'ENTRY':{**W['ENTRY'],'state':write}}
  return t,w
 def test_no_uncertain_entry_allows_worker_to_continue(self):
  r=FakeReader()
  x=worker_uncertain_entry_guard('.',r,pending=[])
  self.assertTrue(x['passNewEntries']);self.assertEqual(r.calls,0)
 def test_already_protected_excluded_from_veto(self):
  r=FakeReader();x=worker_uncertain_entry_guard('.',r,pending=[self.item('PROTECTED')])
  self.assertTrue(x['passNewEntries']);self.assertEqual(r.calls,0)
 def test_response_received_not_retried_by_audit(self):
  r=FakeReader();x=worker_uncertain_entry_guard('.',r,pending=[self.item(write='RESPONSE_RECEIVED')])
  self.assertTrue(x['passNewEntries']);self.assertEqual(r.calls,0)
 def test_uncertain_entry_identified_but_blocks_new_entries_even_with_tp(self):
  r=FakeReader()
  with patch('weex_execution_readonly.pages',side_effect=[[O],[]]):
   x=worker_uncertain_entry_guard('.',r,pending=[self.item()])
  self.assertFalse(x['passNewEntries'])
  self.assertEqual(x['cases'][0]['recoveryState'],'ENTRY_AND_TP_CORROBORATED')
  self.assertEqual(x['newExchangeWrites'],0)
 def test_uncertain_not_found_blocks(self):
  r=FakeReader()
  with patch('weex_execution_readonly.pages',side_effect=[[],[]]):
   x=worker_uncertain_entry_guard('.',r,pending=[self.item()])
  self.assertFalse(x['passNewEntries'])
  self.assertEqual(x['cases'][0]['recoveryState'],'UNRESOLVED')
 def test_unprotected_blocks(self):
  r=FakeReader(algos=[])
  with patch('weex_execution_readonly.pages',side_effect=[[O],[]]):
   x=worker_uncertain_entry_guard('.',r,pending=[self.item()])
  self.assertFalse(x['passNewEntries'])
  self.assertEqual(x['cases'][0]['recoveryState'],'OPEN_UNPROTECTED_REVIEW')
 def test_api_unavailable_blocks(self):
  r=FakeReader()
  with patch('weex_execution_readonly.pages',side_effect=RuntimeError('API_UNAVAILABLE')):
   x=worker_uncertain_entry_guard('.',r,pending=[self.item()])
  self.assertFalse(x['passNewEntries'])
  self.assertEqual(x['cases'][0]['reason'],'READBACK_FAILED_RuntimeError')
 def test_unresolved_has_no_write_permission(self):
  r=FakeReader()
  with patch('weex_execution_readonly.pages',side_effect=[[O],[]]):
   x=worker_uncertain_entry_guard('.',r,pending=[self.item()])
  self.assertTrue(x['readOnly']);self.assertEqual(x['newExchangeWrites'],0)
if __name__=='__main__':unittest.main()
