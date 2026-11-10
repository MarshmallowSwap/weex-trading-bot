"""Simulation of isolated pilot intent, crash restart and readback guard."""
import sqlite3,tempfile,unittest
from pathlib import Path
from contextlib import closing
from weex_isolated_pilot_offline_journal import reserve,review,connect
class PilotJournal(unittest.TestCase):
 def test_persistent_reservation_survives_restart_and_prevents_duplicate(self):
  with tempfile.TemporaryDirectory() as temp:
   db=Path(temp)/'pilot.sqlite3'
   first=reserve(db,pilot_id='trial-1',side='LONG',quantity='0.002',stop_price='2100')
   self.assertFalse(first['maySend'])
   second=reserve(db,pilot_id='trial-1',side='LONG',quantity='0.002',stop_price='2100')
   self.assertTrue(second['reservedPreviously'])
   self.assertFalse(second['maySend'])
   with closing(connect(db)) as c:
    rows=c.execute('SELECT count(*) FROM pilot_v1').fetchone()[0]
   self.assertEqual(rows,1)
 def test_no_evidence_never_allows_order(self):
  with tempfile.TemporaryDirectory() as temp:
   db=Path(temp)/'pilot.sqlite3'
   reserve(db,pilot_id='x',side='SHORT',quantity='0.002',stop_price='2300')
   self.assertEqual(review(db,'x')['state'],'RECONCILIATION_REQUIRED')
 def test_full_exact_readback_and_reduction_only(self):
  with tempfile.TemporaryDirectory() as temp:
   db=Path(temp)/'pilot.sqlite3'
   reserve(db,pilot_id='x',side='LONG',quantity='0.002',stop_price='2100')
   with closing(connect(db)) as c:
    row=c.execute('SELECT entry_id,stop_id FROM pilot_v1 WHERE pilot_id=?',('x',)).fetchone()
   position={'symbol':'ETHUSDT','side':'LONG','size':'0.002'}
   fills=[{'clientOrderId':row[0],'qty':'0.002'}]
   stop={'symbol':'ETHUSDT','clientAlgoId':row[1],'positionSide':'LONG',
         'quantity':'0.002','reduceOnly':True,'algoStatus':'UNTRIGGERED'}
   ok=review(db,'x',position=position,entry_fills=fills,stop_order=stop)
   self.assertEqual(ok['state'],'OBSERVATION_MATCHED_NO_SEND')
   self.assertFalse(ok['maySend'])
   bad=review(db,'x',position=position,entry_fills=fills,stop_order={**stop,'reduceOnly':False})
   self.assertEqual(bad['state'],'REVIEW_REQUIRED')
   mismatch=review(db,'x',position={**position,'size':'0.001'},entry_fills=fills,stop_order=stop)
   self.assertEqual(mismatch['state'],'REVIEW_REQUIRED')
 def test_wrong_symbol_or_quantity_refused(self):
  with tempfile.TemporaryDirectory() as temp:
   db=Path(temp)/'pilot.sqlite3'
   with self.assertRaises(ValueError):reserve(db,pilot_id='x',side='LONG',quantity='1',stop_price='2100')
   with self.assertRaises(ValueError):reserve(db,pilot_id='x',side='FLAT',quantity='.002',stop_price='2100')
if __name__=='__main__':unittest.main()
