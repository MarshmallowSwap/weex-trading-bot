import json,tempfile,unittest
from pathlib import Path
from contextlib import closing
from weex_isolated_pilot_offline_journal import reserve,connect
from weex_pilot_dispatch_reconciliation import reconcile

def setup(db):
    reserve(db,pilot_id='P',side='LONG',quantity='0.002',stop_price='2100')
    with closing(connect(db)) as c:
        entry,close=c.execute('SELECT entry_id,close_id FROM pilot_v1').fetchone()
        c.execute("""CREATE TABLE pilot_entry_dispatch_v1(
          pilot_id TEXT PRIMARY KEY,client_id TEXT UNIQUE NOT NULL,state TEXT,response TEXT)""")
        c.execute("""CREATE TABLE pilot_close_dispatch_v1(
          pilot_id TEXT PRIMARY KEY,close_client_id TEXT UNIQUE NOT NULL,state TEXT,payload TEXT,response TEXT)""")
        c.execute('INSERT INTO pilot_entry_dispatch_v1 VALUES(?,?,?,NULL)',
                  ('P',entry,'ACK_RECEIVED_UNRECONCILED'))
        c.commit()
    return entry,close
def evidence(cid,stage):
    isclose=stage=='close';side='SELL' if isclose else 'BUY'
    order={'clientOrderId':cid,'orderId':'O-close' if isclose else 'O-entry',
           'symbol':'ETHUSDT','positionSide':'LONG','side':side,
           'type':'MARKET','status':'FILLED','executedQty':'0.002','reduceOnly':isclose}
    fills=[{'id':'f-close' if isclose else 'f-entry','orderId':order['orderId'],
           'symbol':'ETHUSDT','positionSide':'LONG','side':side,'qty':'0.002'}]
    positions=[] if isclose else [{'id':'pos1','symbol':'ETHUSDT','side':'LONG',
                                   'size':'0.002','marginType':'ISOLATED'}]
    return order,fills,positions
def run(db,stage,order,fills,pos):
    return reconcile(db,'P',stage,order=order,fills=fills,positions=pos,
                    regular_orders=[],conditional_orders=[])
class Reconciliation(unittest.TestCase):
    def test_entry_then_close_exact_weex_evidence(self):
        with tempfile.TemporaryDirectory() as t:
            db=Path(t)/'p.sqlite3';entry,close=setup(db)
            o,f,p=evidence(entry,'entry')
            r=run(db,'entry',o,f,p)
            self.assertTrue(r['confirmed'],r)
            self.assertFalse(r['canSendNextStage'])
            self.assertTrue(r['requiresOwnershipAttestation'])
            with closing(connect(db)) as c:
                self.assertEqual(c.execute('SELECT state FROM pilot_v1').fetchone()[0],
                                 'ENTRY_RECONCILED_EXTERNALLY')
                c.execute('INSERT INTO pilot_close_dispatch_v1 VALUES(?,?,?,?,NULL)',
                          ('P',close,'ACK_RECEIVED_UNRECONCILED','{}'))
                c.commit()
            o,f,p=evidence(close,'close')
            r=run(db,'close',o,f,p)
            self.assertTrue(r['confirmed'],r)
            with closing(connect(db)) as c:
                self.assertEqual(c.execute('SELECT state FROM pilot_v1').fetchone()[0],
                                 'CLOSED_VERIFIED_EXTERNALLY')
    def test_missing_order_does_not_certify(self):
        with tempfile.TemporaryDirectory() as t:
            db=Path(t)/'p.sqlite3';entry,close=setup(db)
            self.assertFalse(run(db,'entry',None,[],[])['confirmed'])
    def test_unrelated_order_cannot_certify(self):
        with tempfile.TemporaryDirectory() as t:
            db=Path(t)/'p.sqlite3';entry,close=setup(db)
            o,f,p=evidence(entry,'entry');o['clientOrderId']='manual'
            self.assertFalse(run(db,'entry',o,f,p)['confirmed'])
    def test_open_position_prevents_close_confirmation(self):
        with tempfile.TemporaryDirectory() as t:
            db=Path(t)/'p.sqlite3';entry,close=setup(db)
            with closing(connect(db)) as c:
                c.execute('INSERT INTO pilot_close_dispatch_v1 VALUES(?,?,?,?,NULL)',
                          ('P',close,'ACK_RECEIVED_UNRECONCILED','{}'));c.commit()
            o,f,p=evidence(close,'close')
            p=[{'symbol':'ETHUSDT'}]
            self.assertFalse(run(db,'close',o,f,p)['confirmed'])
    def test_duplicate_fill_prevents_confirmation(self):
        with tempfile.TemporaryDirectory() as t:
            db=Path(t)/'p.sqlite3';entry,close=setup(db)
            o,f,p=evidence(entry,'entry');f=f+f
            self.assertFalse(run(db,'entry',o,f,p)['confirmed'])
if __name__=='__main__':unittest.main()
