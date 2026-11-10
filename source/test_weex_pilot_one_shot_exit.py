import tempfile,unittest
from pathlib import Path
from weex_isolated_pilot_offline_journal import reserve,connect
from weex_pilot_one_shot_exit import simulate_close_once,validated_close_payload
from contextlib import closing
class Fake:
 simulation_only=True
 def __init__(self):self.calls=0
 def simulate(self,op,p):
  self.calls+=1
  return {'success':True,'orderId':'FAKE-CLOSE-1'}
class OneShot(unittest.TestCase):
 def test_valid_close_serialized_then_exactly_once(self):
  with tempfile.TemporaryDirectory() as t:
   db=Path(t)/'test.sqlite3'
   reserve(db,pilot_id='once',side='LONG',quantity='.002',stop_price='2100')
   with closing(connect(db)) as c:
    c.execute("UPDATE pilot_v1 SET state='STOP_RECONCILED_EXTERNALLY'")
    c.commit()
   gateway=Fake()
   first=simulate_close_once(db,'once',gateway)
   second=simulate_close_once(db,'once',gateway)
   self.assertEqual(first['state'],'SIMULATED_ACK_ONLY')
   self.assertEqual(second['state'],'ALREADY_HANDLED_NO_RETRY')
   self.assertEqual(gateway.calls,1)
   self.assertFalse(first['canRetry'])
 def test_production_switch_running_blocks(self):
  with tempfile.TemporaryDirectory() as t:
   with self.assertRaises(PermissionError):
    simulate_close_once(Path(t)/'x.sqlite3','once',Fake(),production_mode='RUNNING')
 def test_no_real_gateway_accepted(self):
  with tempfile.TemporaryDirectory() as t:
   with self.assertRaises(PermissionError):
    simulate_close_once(Path(t)/'x.sqlite3','once',object())
 def test_reduce_only_mandatory(self):
  with self.assertRaises(ValueError):
   validated_close_payload({'symbol':'ETHUSDT'})
 def test_wrong_side_mandatory(self):
  p={'symbol':'ETHUSDT','side':'BUY','positionSide':'LONG','type':'MARKET',
     'quantity':'0.002','reduceOnly':True,'newClientOrderId':'wxpilot_x'}
  with self.assertRaises(ValueError):validated_close_payload(p)
if __name__=='__main__':unittest.main()
