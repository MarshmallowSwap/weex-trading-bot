"""Entry reconciliation must accept exactly one authentic protective stop."""
import json,tempfile,unittest
from pathlib import Path
from contextlib import closing
from weex_isolated_pilot_offline_journal import reserve,connect
from weex_pilot_attach_atomic_stop import attach
from weex_pilot_dispatch_reconciliation import reconcile

def evidence(db):
    reserve(db,pilot_id='P',side='LONG',quantity='0.002',stop_price='2100')
    p=attach(db,'P',stop='2100',reference_price='2200')
    with closing(connect(db)) as c:
        c.execute('''CREATE TABLE pilot_entry_dispatch_v1(pilot_id TEXT PRIMARY KEY,
                   client_id TEXT,state TEXT,response TEXT)''')
        c.execute('INSERT INTO pilot_entry_dispatch_v1 VALUES (?,?,?,NULL)',
                  ('P',p['newClientOrderId'],'ACK_RECEIVED_UNRECONCILED'))
        c.commit()
    order={**p,'clientOrderId':p['newClientOrderId'],
           'orderId':'O-1','executedQty':'0.002','status':'FILLED'}
    fills=[{'id':'F-1','orderId':'O-1','symbol':'ETHUSDT',
            'side':'BUY','positionSide':'LONG','qty':'0.002'}]
    positions=[{'id':'123','symbol':'ETHUSDT','side':'LONG','size':'0.002','marginType':'ISOLATED'}]
    stop={'algoId':'98765','clientAlgoId':p['newClientOrderId']+'sl',
          'actualOrderId':'O-1','symbol':'ETHUSDT','side':'SELL',
          'positionSide':'LONG','reduceOnly':True,'workingType':'MARK_PRICE',
          'orderType':'STOP_MARKET','algoStatus':'UNTRIGGERED',
          'triggerPrice':'2100','quantity':'0.002'}
    return order,fills,positions,stop

class ProtectedReconcile(unittest.TestCase):
 def test_exact_protected_entry(self):
  with tempfile.TemporaryDirectory() as td:
   db=Path(td)/'p.sqlite3';o,f,p,sl=evidence(db)
   result=reconcile(db,'P','entry',order=o,fills=f,positions=p,regular_orders=[],conditional_orders=[sl])
   self.assertTrue(result['confirmed'],result)
 def test_other_stop_rejected(self):
  with tempfile.TemporaryDirectory() as td:
   db=Path(td)/'p.sqlite3';o,f,p,sl=evidence(db)
   r=reconcile(db,'P','entry',order=o,fills=f,positions=p,regular_orders=[],
               conditional_orders=[{**sl,'quantity':'0.003'}])
   self.assertFalse(r['confirmed'])
 def test_no_stop_rejected(self):
  with tempfile.TemporaryDirectory() as td:
   db=Path(td)/'p.sqlite3';o,f,p,sl=evidence(db)
   r=reconcile(db,'P','entry',order=o,fills=f,positions=p,regular_orders=[],conditional_orders=[])
   self.assertFalse(r['confirmed'])
if __name__=='__main__':unittest.main()
