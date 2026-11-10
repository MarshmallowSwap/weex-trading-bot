import tempfile,unittest,json
from pathlib import Path
from contextlib import closing
from unittest.mock import patch
import requests
from weex_isolated_pilot_offline_journal import reserve,connect
from weex_pilot_attach_atomic_stop import attach
from weex_pilot_protected_entry_sdk import ProtectedEntryTransport
from weex_pilot_guarded_entry_dispatch import send_entry_once
class Capture:
 def __init__(self): self.count=0;self.payload=None
 def request(self,method,url,**kw):
  self.count+=1;self.payload=json.loads(kw['data'])
  assert method=='POST' and url=='https://api-contract.weex.com/capi/v3/order'
  r=requests.Response();r.status_code=200
  r._content=b'{"success":true,"orderId":"FAKE_ORDER"}'
  r.headers['Content-Type']='application/json'
  return r
def prepare(root,enabled=True):
 cfg={'exchange':'WEEX','marginMode':'ISOLATED','leverage':1,'maxNewOrders':1,
  'maxAdditionalNotionalUSDT':'5','executionEnabled':enabled,
  'liveOrderSubmissionAllowed':enabled,'stopLossVerified':enabled,
  'reduceOnlyCloseVerified':enabled,'requireExplicitTestOrderApproval':True}
 (root/'weex_live_1x_pilot_config.json').write_text(json.dumps(cfg))
 (root/'weex_credentials.json').write_text(json.dumps({
  'api_key':'FAKE','secret_key':'FAKE','passphrase':'FAKE'}))
 db=root/'test.sqlite3';reserve(db,pilot_id='p',side='LONG',quantity='0.002',stop_price='2100')
 payload=attach(db,'p',stop='2100',reference_price='2200')
 account={'fresh':True,'isolatedLeverage':1,'marginMode':'ISOLATED',
          'positions':[],'regularOrders':[],'conditionalOrders':[]}
 return db,payload,account
class Protected(unittest.TestCase):
 def test_sdk_exact_one_shot_with_stop(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);db,p,a=prepare(root);capture=Capture()
   sdk=ProtectedEntryTransport(root,authorization=lambda op,x:op=='post_capi_v3_order' and x==p,
                               session_factory=lambda:capture)
   with patch('live_control.state',return_value={'mode':'STOPPED'}),patch('live_control.build_errors',return_value=[]):
    r=send_entry_once(db,'p',ask='2200',account=a,transport=sdk)
    second=send_entry_once(db,'p',ask='2200',account=a,transport=sdk)
   self.assertEqual(r['state'],'ACK_RECEIVED_UNRECONCILED')
   self.assertEqual(second['state'],'ALREADY_RESERVED_NO_RETRY')
   self.assertEqual(capture.count,1)
   self.assertEqual(capture.payload['slTriggerPrice'],'2100')
   self.assertEqual(capture.payload['SlWorkingType'],'MARK_PRICE')
 def test_disabled_no_send(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);db,p,a=prepare(root,enabled=False);capture=Capture()
   sdk=ProtectedEntryTransport(root,authorization=lambda op,x:True,session_factory=lambda:capture)
   with patch('live_control.state',return_value={'mode':'STOPPED'}),patch('live_control.build_errors',return_value=[]):
    with self.assertRaises(PermissionError):send_entry_once(db,'p',ask='2200',account=a,transport=sdk)
   self.assertEqual(capture.count,0)
 def test_missing_stop_refused_before_send(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);db,p,a=prepare(root);capture=Capture()
   with closing(connect(db)) as c:
    raw=json.loads(c.execute('SELECT proposals FROM pilot_v1').fetchone()[0])
    raw['entry'].pop('slTriggerPrice')
    c.execute('UPDATE pilot_v1 SET proposals=?',(json.dumps(raw),));c.commit()
   sdk=ProtectedEntryTransport(root,authorization=lambda op,x:True,session_factory=lambda:capture)
   with self.assertRaises(ValueError):send_entry_once(db,'p',ask='2200',account=a,transport=sdk)
   self.assertEqual(capture.count,0)
if __name__=='__main__':unittest.main()
