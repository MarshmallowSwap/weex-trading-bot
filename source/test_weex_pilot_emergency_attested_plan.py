import tempfile,unittest
from pathlib import Path
from contextlib import closing
from weex_isolated_pilot_offline_journal import reserve,connect
from weex_pilot_emergency_attested_plan import assess

def fixtures(db):
    reserve(db,pilot_id='P1',side='LONG',quantity='0.002',stop_price='2100')
    with closing(connect(db)) as c:
        cid=c.execute('SELECT entry_id FROM pilot_v1').fetchone()[0]
        c.execute("UPDATE pilot_v1 SET state='ENTRY_RECONCILED_EXTERNALLY'")
        c.commit()
    baseline={'account':'CURRENT_WEEX','snapshotVerified':True,
              'observedAtMs':1000,'positions':[],'regularOrders':[],'conditionalOrders':[]}
    position={'id':'123456789','symbol':'ETHUSDT','side':'LONG','size':'0.002',
              'marginType':'ISOLATED','createdTime':2000}
    entry={'orderId':'9988','clientOrderId':cid,'symbol':'ETHUSDT','positionSide':'LONG',
           'side':'BUY','status':'FILLED','executedQty':'0.002','time':1800}
    fills=[{'id':'fill-x','orderId':'9988','symbol':'ETHUSDT','positionSide':'LONG',
            'side':'BUY','qty':'0.002','time':2100}]
    return baseline,position,entry,fills
def call(db,baseline,pos,entry,fills,**overrides):
    fields={'baseline':baseline,'positions':[pos],'regular_orders':[],
            'conditional_orders':[],'entry_order':entry,'entry_fills':fills}
    fields.update(overrides)
    return assess(db,'P1',**fields)

class EmergencyAttested(unittest.TestCase):
    def test_exact_baseline_and_identity_creates_offline_plan(self):
        with tempfile.TemporaryDirectory() as td:
            db=Path(td)/'p.db';b,p,o,f=fixtures(db)
            result=call(db,b,p,o,f)
            self.assertTrue(result['prepared'],result)
            self.assertFalse(result['canSend'])
            self.assertEqual(result['payload'],{'symbol':'ETHUSDT','positionId':123456789})
    def test_different_client_id_denied(self):
        with tempfile.TemporaryDirectory() as td:
            db=Path(td)/'p.db';b,p,o,f=fixtures(db)
            self.assertFalse(call(db,b,p,{**o,'clientOrderId':'manual'},f)['prepared'])
    def test_existing_manual_order_denied(self):
        with tempfile.TemporaryDirectory() as td:
            db=Path(td)/'p.db';b,p,o,f=fixtures(db)
            self.assertFalse(call(db,b,p,o,f,regular_orders=[{'symbol':'ETHUSDT'}])['prepared'])
    def test_competing_close_denied(self):
        with tempfile.TemporaryDirectory() as td:
            db=Path(td)/'p.db';b,p,o,f=fixtures(db)
            with closing(connect(db)) as c:
                c.execute('CREATE TABLE pilot_close_dispatch_v1(pilot_id TEXT PRIMARY KEY)')
                c.execute('INSERT INTO pilot_close_dispatch_v1 VALUES (?)',('P1',))
                c.commit()
            self.assertFalse(call(db,b,p,o,f)['prepared'])
    def test_fake_position_identity_denied(self):
        with tempfile.TemporaryDirectory() as td:
            db=Path(td)/'p.db';b,p,o,f=fixtures(db)
            self.assertFalse(call(db,b,{**p,'size':'0.005'},o,f)['prepared'])
    def test_no_baseline_denied(self):
        with tempfile.TemporaryDirectory() as td:
            db=Path(td)/'p.db';b,p,o,f=fixtures(db)
            self.assertFalse(call(db,None,p,o,f)['prepared'])
if __name__=='__main__': unittest.main()
