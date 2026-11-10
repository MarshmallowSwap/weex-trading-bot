import unittest
from demo_first_order_gate import assess
class T(unittest.TestCase):
 def test_safe_no_exit(self):self.assertFalse(assess(balance_ok=True,positions_ok=True,history_ok=True,exit_procedure_verified=False,client_binding_ready=True,request_demo_only=True)["orderAuthorized"])
 def test_live_route(self):self.assertFalse(assess(balance_ok=True,positions_ok=True,history_ok=True,exit_procedure_verified=True,client_binding_ready=True,request_demo_only=False)["orderAuthorized"])
 def test_all_prepared(self):self.assertTrue(assess(balance_ok=True,positions_ok=True,history_ok=True,exit_procedure_verified=True,client_binding_ready=True,request_demo_only=True)["orderAuthorized"])
if __name__=="__main__":unittest.main()
