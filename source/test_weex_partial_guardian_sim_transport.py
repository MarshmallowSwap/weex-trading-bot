import io,json,tempfile,unittest
from pathlib import Path
from weex_partial_guardian_persistent import STEPS
from weex_partial_guardian_sim_transport import prepare,send_sim_only,UnsafeWrite,UncertainWrite
class Response:
 def __init__(self):self.status=200;self.data=io.BytesIO(b'[]')
 def __enter__(self):return self
 def __exit__(self,*args):pass
 def read(self,n=-1):return self.data.read(n)
class Fake:
 def __init__(self,fail=False):self.calls=[];self.fail=fail
 def __call__(self,req,timeout):
  self.calls.append((req.get_method(),req.full_url))
  if self.fail:raise TimeoutError('no ack')
  return Response()
class SimTransportTests(unittest.TestCase):
 def setUp(self):
  tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
  self.creds=Path(tmp.name)/'dedicated.json'
  self.creds.write_text(json.dumps({'environment':'WEEX_SIM_V3',
     'api_key':'DUMMY','secret_key':'DUMMY','passphrase':'DUMMY'}))
 def test_stop_market(self):
  method,path,body=prepare(STEPS[0],symbol='BTCUSDT',position_side='LONG',
    quantity='0.0001',client_algo_id='wxsimSLtest',trigger_price='80000',execute_price='0')
  self.assertEqual((method,body['planType'],body['executePrice']),('POST','STOP_LOSS','0'))
  f=Fake()
  r=send_sim_only(STEPS[0],(method,path,body),transport=f,credentials_path=self.creds)
  self.assertEqual(r['status'],'ACK_RECEIVED_READBACK_REQUIRED')
  self.assertTrue(all('api-sim.weex.com' in url for _,url in f.calls))
 def test_tp_limit(self):
  req=prepare(STEPS[3],symbol='BTCUSDT',position_side='LONG',
    quantity='0.0001',client_algo_id='wxsimTPtest',trigger_price='120000',execute_price='120000')
  self.assertEqual(req[2]['executePrice'],'120000')
 def test_exact_cancel(self):
  req=prepare(STEPS[1],symbol='BTCUSDT',position_side='LONG',
    quantity='0.0001',client_algo_id='',exact_algo_id=123)
  f=Fake();send_sim_only(STEPS[1],req,transport=f,credentials_path=self.creds)
  self.assertEqual(f.calls[0][0],'DELETE')
 def test_uncertain_ack_not_retried(self):
  req=prepare(STEPS[0],symbol='BTCUSDT',position_side='LONG',
    quantity='0.0001',client_algo_id='wxsimSLtest',trigger_price='80000',execute_price='0')
  f=Fake(True)
  with self.assertRaises(UncertainWrite):send_sim_only(STEPS[0],req,transport=f,credentials_path=self.creds)
  self.assertEqual(len(f.calls),1)
 def test_wrong_host_unavailable(self):
  req=prepare(STEPS[1],symbol='BTCUSDT',position_side='LONG',
    quantity='0.0001',client_algo_id='',exact_algo_id=123)
  f=Fake()
  with self.assertRaises(UnsafeWrite):send_sim_only(STEPS[0],req,transport=f,credentials_path=self.creds)
  self.assertEqual(len(f.calls),0)
 def test_unsafe_size_refused(self):
  req=prepare(STEPS[0],symbol='BTCUSDT',position_side='LONG',
    quantity='0.1',client_algo_id='wxsimSLtest',trigger_price='80000',execute_price='0')
  with self.assertRaises(UnsafeWrite):send_sim_only(STEPS[0],req,transport=Fake(),credentials_path=self.creds)
 def test_stop_limit_refused(self):
  with self.assertRaises(UnsafeWrite):prepare(STEPS[0],symbol='BTCUSDT',position_side='LONG',
    quantity='0.0001',client_algo_id='wxsimSLtest',trigger_price='80000',execute_price='70000')
 def test_cancel_requires_exact_id(self):
  with self.assertRaises(UnsafeWrite):prepare(STEPS[2],symbol='BTCUSDT',position_side='LONG',
    quantity='0.0001',client_algo_id='',exact_algo_id=None)
if __name__=='__main__':unittest.main()
