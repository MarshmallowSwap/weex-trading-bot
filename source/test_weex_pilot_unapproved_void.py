import tempfile,unittest
from pathlib import Path
from contextlib import closing
from weex_isolated_pilot_offline_journal import reserve,connect
from weex_pilot_unapproved_void import void_unapproved

class VoidUnapproved(unittest.TestCase):
 def test_rejected_approval_releases_clean_reservation(self):
  with tempfile.TemporaryDirectory() as td:
   db=Path(td)/'p.db'
   reserve(db,pilot_id='p1',side='LONG',quantity='0.002',stop_price='2100')
   result=void_unapproved(db,'p1')
   self.assertTrue(result['voided'])
   with closing(connect(db)) as c:
    self.assertEqual(c.execute('SELECT COUNT(*) FROM pilot_v1').fetchone()[0],0)
 def test_dispatched_intent_never_deleted(self):
  with tempfile.TemporaryDirectory() as td:
   db=Path(td)/'p.db'
   reserve(db,pilot_id='p1',side='LONG',quantity='0.002',stop_price='2100')
   with closing(connect(db)) as c:
    c.execute('CREATE TABLE pilot_entry_dispatch_v1(pilot_id TEXT PRIMARY KEY,state TEXT)')
    c.execute("INSERT INTO pilot_entry_dispatch_v1 VALUES('p1','OUTCOME_UNKNOWN')")
    c.commit()
   self.assertEqual(void_unapproved(db,'p1')['reason'],'DISPATCH_MAY_HAVE_OCCURRED')
   with closing(connect(db)) as c:
    self.assertEqual(c.execute('SELECT COUNT(*) FROM pilot_v1').fetchone()[0],1)
 def test_advanced_lifecycle_not_deleted(self):
  with tempfile.TemporaryDirectory() as td:
   db=Path(td)/'p.db'
   reserve(db,pilot_id='p1',side='LONG',quantity='0.002',stop_price='2100')
   with closing(connect(db)) as c:
    c.execute("UPDATE pilot_v1 SET state='ENTRY_RECONCILED_EXTERNALLY'")
    c.commit()
   self.assertEqual(void_unapproved(db,'p1')['reason'],'PILOT_ADVANCED')
if __name__=='__main__':unittest.main()
