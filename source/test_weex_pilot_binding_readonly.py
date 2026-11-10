"""Offline tests for the pilot read-only evidence matcher."""
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from weex_pilot_binding_readonly import inspect
from weex_isolated_pilot_offline_journal import reserve,connect

class MatchingTest(unittest.TestCase):
 def test_missing_journal_denies(self):
  with tempfile.TemporaryDirectory() as tmp:
   r=inspect(Path(tmp)/'none.sqlite3',[])
   self.assertEqual(r['state'],'NO_PILOT_JOURNAL')
   self.assertFalse(r['canSend'])
 def test_verified_fields_never_authorize(self):
  with tempfile.TemporaryDirectory() as tmp:
   db=Path(tmp)/'pilot.sqlite3'
   reserve(db,pilot_id='p1',side='LONG',quantity='.002',stop_price='2100')
   with closing(connect(db)) as c:
    ids=c.execute('SELECT entry_id,stop_id,close_id FROM pilot_v1').fetchone()
   rows=[{'clientOrderId':ids[0],'orderId':'order1','symbol':'ETHUSDT','positionSide':'LONG','origQty':'0.002'},
         {'clientAlgoId':ids[1],'algoId':'algo1','symbol':'ETHUSDT','positionSide':'LONG','quantity':'0.002','reduceOnly':True},
         {'clientOrderId':ids[2],'orderId':'order2','symbol':'ETHUSDT','positionSide':'LONG','origQty':'0.002','executedQty':'0.002','side':'SELL','status':'FILLED','reduceOnly':True}]
   r=inspect(db,rows)
   self.assertEqual([x['state'] for x in r['stages']],['OBSERVED_UNATTESTED']*3)
   self.assertFalse(r['canSend'])
   self.assertFalse(r['canRetry'])
 def test_mismatch_and_duplicates(self):
  with tempfile.TemporaryDirectory() as tmp:
   db=Path(tmp)/'pilot.sqlite3'
   reserve(db,pilot_id='p2',side='SHORT',quantity='.002',stop_price='2500')
   with closing(connect(db)) as c:
    entry=c.execute('SELECT entry_id FROM pilot_v1').fetchone()[0]
   row={'clientOrderId':entry,'orderId':'order1','symbol':'ETHUSDT','positionSide':'SHORT','origQty':'0.003'}
   mismatch=inspect(db,[row])
   self.assertEqual(mismatch['stages'][0]['state'],'MISMATCH')
   duplicate=inspect(db,[row,row])
   self.assertEqual(duplicate['stages'][0]['state'],'AMBIGUOUS')

 def test_reduce_only_close_requires_filled_opposite_side_and_exact_qty(self):
  with tempfile.TemporaryDirectory() as tmp:
   db=Path(tmp)/'pilot.sqlite3'
   reserve(db,pilot_id='exit-check',side='SHORT',quantity='0.002',stop_price='2500')
   with closing(connect(db)) as c:
    cid=c.execute('SELECT close_id FROM pilot_v1').fetchone()[0]
   base={'clientOrderId':cid,'orderId':'close-1','symbol':'ETHUSDT',
         'positionSide':'SHORT','origQty':'0.002','executedQty':'0.002',
         'side':'BUY','status':'FILLED','reduceOnly':True}
   self.assertEqual(inspect(db,[base])['stages'][2]['state'],'OBSERVED_UNATTESTED')
   for changes in ({'reduceOnly':False},{'executedQty':'0.001'},
                   {'side':'SELL'},{'status':'NEW'},{'origQty':'0.003'}):
    row={**base,**changes}
    r=inspect(db,[row])
    self.assertEqual(r['stages'][2]['state'],'MISMATCH')
    self.assertFalse(r['canSend'])

 def test_sdk_reservation_schema(self):
  import sqlite3
  with tempfile.TemporaryDirectory() as tmp:
   db=Path(tmp)/'sdk.sqlite3'
   with closing(sqlite3.connect(db)) as c:
    c.execute('CREATE TABLE reservations(signal_id TEXT PRIMARY KEY,client_id TEXT,symbol TEXT,state TEXT)')
    c.execute("INSERT INTO reservations VALUES('sig1','wxpilot_test','ETHUSDT','SUBMISSION_UNKNOWN')")
    c.commit()
   rows=[{'clientOrderId':'wxpilot_test','orderId':'o123','symbol':'ETHUSDT'}]
   result=inspect(db,rows)
   self.assertEqual(result['state'],'READ_ONLY_SDK_RESERVATION_AUDIT')
   self.assertEqual(result['stages'][0]['state'],'OBSERVED_UNATTESTED')
   self.assertFalse(result['canSend'])
   self.assertFalse(result['canRetry'])
   self.assertEqual(inspect(db,[])['stages'][0]['state'],'UNVERIFIED')

if __name__=='__main__':unittest.main()
