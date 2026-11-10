import tempfile,sqlite3,unittest
from contextlib import closing
from pathlib import Path
from weex_existing_account_1x_pilot_audit import journal_inventory,assess_local
from weex_pilot_journal_bootstrap import initialize

class ExistingAccountPilotTests(unittest.TestCase):
 def test_empty_existing_journal_remains_blocked_by_gate(self):
  with tempfile.TemporaryDirectory() as temp:
   path=Path(temp)/'pilot.sqlite3'
   initialize(path)
   journal=journal_inventory(path)
   self.assertEqual(journal['records'],0)
   out=assess_local({'issues':['INDEPENDENT_GATE_NO_GO'],'orderAuthorized':False},journal,'STOPPED')
   self.assertFalse(out['pilotExecutionAllowed'])
   self.assertIn('INDEPENDENT_GATE_NO_GO',out['blockers'])
 def test_existing_records_are_never_auto_cleared(self):
  with tempfile.TemporaryDirectory() as temp:
   path=Path(temp)/'pilot.sqlite3'
   initialize(path)
   with closing(sqlite3.connect(path)) as c:
    c.execute("INSERT INTO pilot_v1 VALUES('x','LONG','0.002','PREPARED_NO_SEND','e','s','c','{}')")
    c.commit()
   journal=journal_inventory(path)
   out=assess_local({'issues':[],'orderAuthorized':False},journal,'STOPPED')
   self.assertEqual(journal['records'],1)
   self.assertIn('PILOT_JOURNAL_REQUIRES_REVIEW',out['blockers'])
 def test_runtime_running_blocks(self):
  with tempfile.TemporaryDirectory() as temp:
   path=Path(temp)/'pilot.sqlite3';initialize(path)
   out=assess_local({'issues':[],'orderAuthorized':False},journal_inventory(path),'RUNNING')
   self.assertIn('BOT_NOT_STOPPED',out['blockers'])
 def test_missing_journal_is_not_created(self):
  with tempfile.TemporaryDirectory() as temp:
   path=Path(temp)/'missing.sqlite3'
   j=journal_inventory(path)
   self.assertEqual(j['state'],'MISSING')
   self.assertFalse(path.exists())

 def test_unprotected_entry_and_unverified_close_are_explicit_blockers(self):
  with tempfile.TemporaryDirectory() as temp:
   path=Path(temp)/'pilot.sqlite3'
   initialize(path)
   out=assess_local({'issues':['PILOT_STOP_LOSS_NOT_VERIFIED',
    'REDUCE_ONLY_EXIT_NOT_VERIFIED'],'orderAuthorized':False},journal_inventory(path),'STOPPED')
   self.assertFalse(out['stopLossMandatoryForPilot'])
   self.assertNotIn('PILOT_STOP_LOSS_NOT_VERIFIED',out['blockers'])
   self.assertIn('PILOT_WITHOUT_STOP_LOSS_POSITION_CAN_REMAIN_EXPOSED',out['warnings'])
   self.assertIn('NO_VERIFIED_EMERGENCY_CLOSE_PATH',out['blockers'])
   self.assertFalse(out['pilotExecutionAllowed'])

if __name__=='__main__': unittest.main()
