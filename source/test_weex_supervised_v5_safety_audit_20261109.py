"""Regression tests: independent V5 audit must reject unproven live readiness."""
import tempfile,unittest
from pathlib import Path
from weex_supervised_v5_safety_audit_20261109 import audit,FILES,ROOT
class V5AuditTests(unittest.TestCase):
 def test_real_source_is_not_falsely_certified(self):
  report=audit(ROOT)
  self.assertFalse(report['releaseEligible'])
  self.assertNotIn('HARDCODED_EXTERNAL_APPROVAL_TRUE',report['blockingFindings'])
  self.assertNotIn('UNPROVEN_CONTEXT_accountFlat',report['blockingFindings'])
  self.assertIn('READONLY_WATCHDOG_CANNOT_CLOSE',report['blockingFindings'])
  self.assertNotIn('V5_ENTRY_NOT_WIRED_IN_PRODUCTION_WORKER',report['blockingFindings'])
  self.assertIn('REAL_CRASH_ATTESTATION_MISSING',report['blockingFindings'])
 def test_missing_files_fail_closed(self):
  with tempfile.TemporaryDirectory() as td:
   result=audit(Path(td))
   self.assertEqual(result['status'],'BLOCKED')
   self.assertFalse(result['releaseEligible'])
   self.assertEqual(set(result['missing']),set(FILES.values()))
if __name__=='__main__':unittest.main()
