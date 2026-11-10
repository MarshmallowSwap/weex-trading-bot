import tempfile,unittest,json
from pathlib import Path
from contextlib import closing
from weex_isolated_pilot_offline_journal import reserve,connect
from weex_pilot_emergency_reconciliation import reconcile_emergency

def setup(db):
    reserve(db,pilot_id='P',side='LONG',quantity='0.002',stop_price='2100')
    with closing(connect(db)) as c:
        c.execute("UPDATE pilot_v1 SET state='ENTRY_RECONCILED_EXTERNALLY'")
        c.execute("""CREATE TABLE pilot_emergency_dispatch_v1(
            pilot_id TEXT PRIMARY KEY,position_id TEXT UNIQUE,state TEXT,response TEXT)""")
        c.execute("INSERT INTO pilot_emergency_dispatch_v1 VALUES(?,?,?,?)",
                 ('P','123456789','ACK_RECEIVED_NEEDS_EXCHANGE_READBACK',json.dumps({'orderId':'O1'})))
        c.commit()
    order={'orderId':'O1','symbol':'ETHUSDT','positionSide':'LONG','side':'SELL',
           'status':'FILLED','executedQty':'0.002','reduceOnly':True}
    fills=[{'id':'f1','orderId':'O1','symbol':'ETHUSDT',
            'positionSide':'LONG','side':'SELL','qty':'0.002'}]
    return order,fills
def proof(db,o,f,p=None):
    return reconcile_emergency(db,'P',order=o,fills=f,positions=p or [],
                               regular=[],conditional=[])
class EmergencyReadback(unittest.TestCase):
    def test_exact_fill_and_flat(self):
        with tempfile.TemporaryDirectory() as t:
            db=Path(t)/'p.db';o,f=setup(db);r=proof(db,o,f)
            self.assertTrue(r['confirmed'],r)
            with closing(connect(db)) as c:
                self.assertEqual(c.execute('SELECT state FROM pilot_v1').fetchone()[0],
                                 'CLOSED_VERIFIED_EXTERNALLY')
    def test_reject_wrong_order(self):
        with tempfile.TemporaryDirectory() as t:
            db=Path(t)/'p.db';o,f=setup(db);self.assertFalse(proof(db,{**o,'orderId':'O2'},f)['confirmed'])
    def test_reject_not_flat(self):
        with tempfile.TemporaryDirectory() as t:
            db=Path(t)/'p.db';o,f=setup(db)
            self.assertFalse(proof(db,o,f,[{'id':'123456789'}])['confirmed'])
    def test_flat_with_residual_stop_not_marked_closed(self):
        with tempfile.TemporaryDirectory() as t:
            db=Path(t)/'p.db';o,f=setup(db)
            r=reconcile_emergency(db,'P',order=o,fills=f,positions=[],regular=[],
                    conditional=[{'algoId':'orphan','symbol':'ETHUSDT'}])
            self.assertFalse(r['confirmed'])
            self.assertEqual(r['state'],'ACCOUNT_FLAT_BUT_CONDITIONAL_ORDER_REMAINS')
            with closing(connect(db)) as c:
                self.assertEqual(c.execute('SELECT state FROM pilot_v1').fetchone()[0],
                                 'ENTRY_RECONCILED_EXTERNALLY')
    def test_reject_partial_fill(self):
        with tempfile.TemporaryDirectory() as t:
            db=Path(t)/'p.db';o,f=setup(db)
            self.assertFalse(proof(db,o,[{**f[0],'qty':'0.001'}])['confirmed'])
if __name__=='__main__':unittest.main()
