import unittest
from official_weex_live_sdk_adapter import LiveSdkReadOnly,READ_OPERATIONS
class Test(unittest.TestCase):
 def test_order_blocked(self):
  with self.assertRaises(PermissionError):LiveSdkReadOnly().execute("post_capi_v3_order",{})
 def test_close_blocked(self):
  with self.assertRaises(PermissionError):LiveSdkReadOnly().execute("post_capi_v3_close_positions",{})
 def test_leverage_blocked(self):
  with self.assertRaises(PermissionError):LiveSdkReadOnly().execute("post_capi_v3_account_leverage",{})
 def test_unknown_blocked(self):
  with self.assertRaises(PermissionError):LiveSdkReadOnly().execute("get_unknown")
 def test_read_operations(self):
  self.assertIn("get_capi_v3_order_history",READ_OPERATIONS)
if __name__=="__main__":unittest.main()
