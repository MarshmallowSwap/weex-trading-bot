"""Offline audit regression: 1000 trade-to-order identities, checkpoint fail-closed."""
import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import weex_trade_1000_reconciliation as audit
from weex_api_budget import BudgetDeferred

class ThousandIdentity(unittest.TestCase):
 def run_audit(self, missing=0, budget=False):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td)
   trades=[{'id':str(i+1),'orderId':str(50000+i),'symbol':'ETHUSDT','time':1800000000000-i}
           for i in range(1000)]
   snapshot={'checkedAt':'2026-11-08T20:00:00+00:00','trades':trades,'tradeCount':1000}
   (root/'snapshot.json').write_text(json.dumps(snapshot))
   order_rows=[{'orderId':str(50000+i),'symbol':'ETHUSDT','clientOrderId':'owned-'+str(i)}
               for i in range(1000-missing)]
   def fake_query(path):
    if budget:raise BudgetDeferred('WAIT_API_REQUEST_WEIGHT_BUDGET')
    oid=path.rsplit('=',1)[-1]
    return {'orderId':oid,'symbol':'ETHUSDT','clientOrderId':'owned-'+oid}
   with patch.object(audit,'ROOT',root),patch.object(audit,'SNAP',root/'snapshot.json'),patch.object(
       audit,'CKPT',root/'checkpoint.json'),patch.object(audit,'REPORT',root/'report.json'),patch.object(
       audit,'history',return_value={'completeWithinRequestedBounds':True,'orders':order_rows}),patch.object(
       audit,'query',side_effect=fake_query),patch('live_control.state',return_value={'mode':'STOPPED'}),patch(
       'live_control.build_errors',return_value=[]):
    r=audit.run(max_order_lookups=12)
   return r
 def test_complete_1000_order_identity(self):
  r=self.run_audit()
  self.assertEqual(r['matchedTrades'],1000);self.assertTrue(r['all1000TradeOrderIdsVerified'])
  self.assertFalse(r['financialFillNotionalCertified'])
 def test_deferred_exact_lookup_does_not_claim_complete(self):
  r=self.run_audit(missing=3,budget=True)
  self.assertEqual(r['matchedTrades'],997)
  self.assertEqual(r['unmatchedTrades'],3)
  self.assertTrue(r['budgetDeferred'])
  self.assertFalse(r['all1000TradeOrderIdsVerified'])
if __name__=='__main__':unittest.main()
