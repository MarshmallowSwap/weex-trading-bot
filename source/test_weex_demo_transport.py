import io,json,unittest
from weex_demo_transport import DemoTransport
class Response:
 def __enter__(self):return self
 def __exit__(self,*args):return False
 def read(self):return b'{"success":true,"orderId":"123","clientOrderId":"x"}'
P={"symbol":"BTCSUSDT","side":"BUY","positionSide":"LONG","type":"MARKET","quantity":"0.01","newClientOrderId":"x"}
class Tests(unittest.TestCase):
 def test_off(self):
  self.assertFalse(DemoTransport(write_enabled=False).post_order(P)["sent"])
 def test_live_symbol(self):
  self.assertFalse(DemoTransport(write_enabled=True).post_order(dict(P,symbol="BTCUSDT"))["sent"])
 def test_bad(self):
  with self.assertRaises(ValueError):DemoTransport().post_order({})
 def test_no_network(self):
  def fail(*args,**kwargs):raise AssertionError("network called")
  self.assertFalse(DemoTransport(opener=fail).post_order(P)["sent"])
if __name__=="__main__":unittest.main()
