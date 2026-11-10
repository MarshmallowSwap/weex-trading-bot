import json,sqlite3,tempfile,unittest
from contextlib import closing
from pathlib import Path
from weex_multi_symbol_ownership_v12 import classify

def seed(root, rows):
 with closing(sqlite3.connect(Path(root)/'weex_user_live_lifecycle.sqlite3')) as db:
  db.execute('CREATE TABLE trades_v1 (id TEXT,symbol TEXT,state TEXT,owned TEXT,plan TEXT)')
  db.execute('CREATE TABLE writes_v1 (trade_id TEXT,kind TEXT,state TEXT)')
  for tid,symbol,state,source,pid in rows:
   db.execute('INSERT INTO trades_v1 VALUES (?,?,?,?,?)',(
     tid,symbol,state,json.dumps({'positionId':pid,'entrySource':source}),
     json.dumps({'entrySource':source})))
   db.execute('INSERT INTO writes_v1 VALUES (?,?,?)',(tid,'ENTRY','ACK'))
  db.commit()
P=lambda id,sym:{'id':id,'symbol':sym,'side':'LONG'}
class MultiOwnership(unittest.TestCase):
 def test_multi_symbol_automatic_telegram_unattributed(self):
  with tempfile.TemporaryDirectory() as td:
   seed(td,[('a','BTCUSDT','PROTECTED','automatic','101'),
            ('b','ETHUSDT','PROTECTED','manual_telegram','102')])
   x=classify(td,[P('101','BTCUSDT'),P('102','ETHUSDT'),P('103','AINUSDT')],[],[])
   self.assertEqual(x['automaticPositionIds'],['101'])
   self.assertEqual(x['telegramPositionIds'],['102'])
   self.assertEqual(x['unattributedPositionIds'],['103'])
   self.assertFalse(x['entryAllowed'])
   self.assertTrue(x['crossSharedCollateral'])
 def test_missing_journal_never_claims_ownership(self):
  with tempfile.TemporaryDirectory() as td:
   x=classify(td,[P('101','BTCUSDT')],[],[])
   self.assertEqual(x['status'],'JOURNAL_UNAVAILABLE')
   self.assertEqual(x['automaticPositionIds'],[])
 def test_terminal_or_unrecognized_source_not_owned(self):
  with tempfile.TemporaryDirectory() as td:
   seed(td,[('a','BTCUSDT','CLOSED','automatic','101'),
            ('b','ETHUSDT','PROTECTED','EXTERNAL','102')])
   x=classify(td,[P('101','BTCUSDT'),P('102','ETHUSDT')],[],[])
   self.assertEqual(set(x['unattributedPositionIds']),{'101','102'})
 def test_conflicting_position_id_fails(self):
  with tempfile.TemporaryDirectory() as td:
   seed(td,[('a','BTCUSDT','PROTECTED','automatic','101'),
            ('b','BTCUSDT','PROTECTED','manual_telegram','101')])
   x=classify(td,[P('101','BTCUSDT')],[],[])
   self.assertEqual(x['status'],'CONFLICT')
   self.assertEqual(x['conflictedPositionIds'],['101'])
 def test_exchange_symbol_mismatch_fails(self):
  with tempfile.TemporaryDirectory() as td:
   seed(td,[('a','BTCUSDT','PROTECTED','automatic','101')])
   x=classify(td,[P('101','ETHUSDT')],[],[])
   self.assertEqual(x['status'],'CONFLICT')
 def test_unknown_id_and_duplicate_exchange_id_fails(self):
  with tempfile.TemporaryDirectory() as td:
   seed(td,[])
   x=classify(td,[P(None,'ETHUSDT'),P('101','BTCUSDT'),P('101','ETHUSDT')],[],[])
   self.assertEqual(x['status'],'CONFLICT')
 def test_invalid_exchange_snapshot_fails_closed(self):
  with tempfile.TemporaryDirectory() as td:
   seed(td,[])
   with self.assertRaises(ValueError):classify(td,[{'id':'11'}],[],[])
if __name__=='__main__':unittest.main()
