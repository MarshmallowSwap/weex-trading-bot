"""Offline bootstrap assertions: no fabricated trades and idempotent journal."""
import tempfile,unittest
from pathlib import Path
from weex_pilot_journal_bootstrap import initialize
from weex_pilot_binding_readonly import inspect

class BootstrapTests(unittest.TestCase):
 def test_initialization_empty_and_idempotent(self):
  with tempfile.TemporaryDirectory() as folder:
   p=Path(folder)/'pilot.sqlite3'
   a=initialize(p)
   b=initialize(p)
   self.assertEqual((a['pilotRecords'],b['pilotRecords']),(0,0))
   self.assertFalse(b['canSend'])
   self.assertEqual(inspect(p,[])['state'],'READ_ONLY_AUDIT')
   self.assertEqual(inspect(p,[])['pilots'],0)
 def test_existing_pilot_never_deleted(self):
  from weex_isolated_pilot_offline_journal import reserve
  with tempfile.TemporaryDirectory() as folder:
   p=Path(folder)/'pilot.sqlite3'
   initialize(p)
   reserve(p,pilot_id='persist',side='LONG',quantity='0.002',stop_price='2100')
   self.assertEqual(initialize(p)['pilotRecords'],1)
   self.assertEqual(inspect(p,[])['pilots'],1)
   self.assertTrue(all(s['state']=='UNVERIFIED' for s in inspect(p,[])['stages']))

if __name__=='__main__':unittest.main()
