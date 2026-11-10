import tempfile,unittest
from weex_api_budget import Budget,BudgetDeferred

class CancelBudgetTests(unittest.TestCase):
    def test_conditional_cancel_cost_and_limit(self):
        with tempfile.TemporaryDirectory() as root:
            b=Budget(root,clock=lambda:1000)
            b.install_rate_limits([{'rateLimitType':'REQUEST_WEIGHT','interval':'MINUTE','intervalNum':1,'limit':1}])
            self.assertEqual(b.reserve('DELETE','https://api-contract.weex.com/capi/v3/algoOrder?orderId=42'),1)
            self.assertEqual(b.used()['weight'],1)
            with self.assertRaises(BudgetDeferred):b.reserve('DELETE','https://api-contract.weex.com/capi/v3/algoOrder?orderId=43')
    def test_bulk_cancel_remains_unclassified(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(BudgetDeferred):Budget(root).reserve('DELETE','https://api-contract.weex.com/capi/v3/algoOpenOrders')
