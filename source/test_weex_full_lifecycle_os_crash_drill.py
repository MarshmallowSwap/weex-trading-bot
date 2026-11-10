"""Cross-process crash drill assertions, no WEEX calls."""
import unittest
from weex_full_lifecycle_os_crash_drill import run
class FullLifecycleCrash(unittest.TestCase):
 def test_four_actual_process_deaths_and_safe_state(self):
  r=run();rows={x['crashPoint']:x for x in r['results']}
  self.assertEqual(set(rows),{'ENTRY_BEFORE_SEND','ENTRY_AFTER_SEND','TP_BEFORE_SEND','TP_AFTER_SEND'})
  self.assertEqual(rows['ENTRY_BEFORE_SEND']['postRestartState'],'REVIEW_REQUIRED')
  self.assertEqual(rows['ENTRY_BEFORE_SEND']['afterEntryWrites'],0)
  self.assertEqual(rows['ENTRY_AFTER_SEND']['postRestartState'],'PROTECTED')
  self.assertEqual(rows['ENTRY_AFTER_SEND']['afterEntryWrites'],1)
  self.assertEqual(rows['ENTRY_AFTER_SEND']['afterTpWrites'],1)
  self.assertEqual(rows['TP_BEFORE_SEND']['postRestartState'],'TP_PENDING')
  self.assertEqual(rows['TP_BEFORE_SEND']['afterTpWrites'],0)
  self.assertEqual(rows['TP_AFTER_SEND']['postRestartState'],'PROTECTED')
  self.assertEqual(rows['TP_AFTER_SEND']['afterTpWrites'],1)
  self.assertTrue(all(x['noDuplicateWrite'] for x in r['results']))
  self.assertFalse(r['realWEEXCrashTested'])
  self.assertEqual(r['exchangeWrites'],0)
if __name__=='__main__':unittest.main()
