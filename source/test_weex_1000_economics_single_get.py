"""Offline-only proof that fully observed snapshot fills need just one parent GET."""
import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import weex_trade_1000_economics_incremental as mod
class FakeBudget:
 def __init__(self,weight):self.weight=weight
 def used(self):return {'weight':self.weight}
class EconomicReadBudget(unittest.TestCase):
 def test_full_snapshot_order_one_get(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td)
   t=[{'id':i+1,'orderId':1000+i,'symbol':'ETHUSDT','side':'BUY',
       'positionSide':'LONG','qty':'1','price':'10','quoteQty':'10',
       'commission':'0.01','commissionAsset':'USDT','time':1800000000000-i}
       for i in range(1000)]
   stamp='scope1'
   (root/'snapshot.json').write_text(json.dumps({'checkedAt':stamp,'trades':t}))
   (root/'orders.json').write_text(json.dumps({'snapshotAt':stamp,
       'statusByOrder':{str(1000+i):{'matched':True} for i in range(1000)}}))
   # This script intentionally requires exactly 137 unique IDs; replace
   # the artificial 1000 orders with 137, while keeping exactly 1000 fills.
   for i,fill in enumerate(t):
    fill['orderId']=1000+(i%137)
   (root/'snapshot.json').write_text(json.dumps({'checkedAt':stamp,'trades':t}))
   (root/'orders.json').write_text(json.dumps({'snapshotAt':stamp,
       'statusByOrder':{str(1000+i):{'matched':True} for i in range(137)}}))
   from decimal import Decimal as D
   calls=[]
   def fake_query(path):
    calls.append(path)
    if '/userTrades?' in path:raise AssertionError('UNNECESSARY_FILL_GET')
    oid=int(path.rsplit('=',1)[-1])
    qty=sum(D(x['qty']) for x in t if x['orderId']==oid)
    return {'orderId':oid,'symbol':'ETHUSDT','side':'BUY','positionSide':'LONG',
      'type':'MARKET','status':'FILLED','executedQty':str(qty),
      'avgPrice':'10','cumQuote':str(qty*10)}
   with patch.object(mod,'ROOT',root),patch.object(mod,'SNAP',root/'snapshot.json'),patch.object(
     mod,'ORDER_CK',root/'orders.json'),patch.object(mod,'CK',root/'economics.json'),patch.object(
     mod,'REPORT',root/'report.json'),patch.object(mod,'query',side_effect=fake_query),patch.object(
     mod,'budget',return_value=FakeBudget(100)),patch(
     'live_control.state',return_value={'mode':'STOPPED'}),patch('live_control.build_errors',return_value=[]):
    result=mod.run(max_orders=12)
   self.assertEqual(result['ordersVerified'],12)
   self.assertEqual(len(calls),12)
   self.assertTrue(all('/capi/v3/order?' in x for x in calls))
if __name__=='__main__':unittest.main()
