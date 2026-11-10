"""Readback integration failure tests, zero network and dummy credentials."""
import io,json,tempfile,unittest
from pathlib import Path
from weex_partial_guardian_sim_readback import snapshot,SnapshotFailure,guardian_readback
from weex_partial_guardian_persistent import register
from test_weex_partial_guardian_replay import B,POS,OTP,OSL
class Response:
 def __init__(self,data,status=200):self.raw=io.BytesIO(json.dumps(data).encode());self.status=status
 def __enter__(self):return self
 def __exit__(self,*args):pass
 def read(self,*args):return self.raw.read(*args)
class Fake:
 def __init__(self,values):self.values=values;self.calls=[]
 def __call__(self,req,timeout):
  self.calls.append((req.full_url,req.get_method()))
  key=next(k for k in self.values if req.full_url.endswith(k))
  value=self.values[key]
  if isinstance(value,Exception):raise value
  if isinstance(value,tuple):return Response(value[1],value[0])
  return Response(value)
class AdapterTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.path=Path(self.tmp.name)/'fake_credentials.json'
  self.path.write_text(json.dumps({'environment':'WEEX_SIM_V3','api_key':'TEST_ONLY',
      'secret_key':'TEST_ONLY','passphrase':'TEST_ONLY'}),encoding='utf-8')
  self.values={'/capi/v3/account/position/allPosition':POS,
               '/capi/v3/openAlgoOrders':[OTP,OSL],'/capi/v3/openOrders':[]}
 def run_snapshot(self):
  return snapshot(transport=Fake(self.values),credentials_path=self.path)
 def test_three_authenticated_get_only(self):
  transport=Fake(self.values)
  r=snapshot(transport=transport,credentials_path=self.path)
  self.assertEqual([x[1] for x in transport.calls],['GET']*3)
  self.assertTrue(all('api-sim.weex.com' in x[0] for x in transport.calls))
  self.assertEqual(r['productionWrites'],0)
 def test_guardian_evaluates_demo_snapshot(self):
  db=Path(self.tmp.name)/'guard.sqlite'
  register(db,'t',**B)
  result=guardian_readback(db,'t',transport=Fake(self.values),credentials_path=self.path)
  self.assertEqual(result['state'],'NEEDS_NEW_STOP_FIRST_OFFLINE')
  self.assertFalse(result['canDispatch'])
 def test_timeout_fail_closed(self):
  self.values['/capi/v3/openAlgoOrders']=TimeoutError('timeout')
  with self.assertRaises(SnapshotFailure):self.run_snapshot()
 def test_http_500_fail_closed(self):
  self.values['/capi/v3/openAlgoOrders']=(500,[])
  with self.assertRaises(SnapshotFailure):self.run_snapshot()
 def test_business_error_dict_fail_closed(self):
  self.values['/capi/v3/openAlgoOrders']={'code':-1049,'msg':'failed'}
  with self.assertRaises(SnapshotFailure):self.run_snapshot()
 def test_truncated_result_blocked(self):
  self.values['/capi/v3/openAlgoOrders']=[{}]*100
  with self.assertRaises(SnapshotFailure):self.run_snapshot()
 def test_invalid_row_blocked(self):
  self.values['/capi/v3/openAlgoOrders']=[1]
  with self.assertRaises(SnapshotFailure):self.run_snapshot()
 def test_missing_file_blocked(self):
  with self.assertRaises(SnapshotFailure):
   snapshot(transport=Fake(self.values),credentials_path=Path(self.tmp.name)/'none.json')
if __name__=='__main__':unittest.main()
