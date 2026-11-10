"""End-to-end authenticated SDK serialization and durable close dispatch tests.

HTTP requests are intercepted in-memory. No exchange endpoint is contacted.
"""
import json,tempfile,unittest
from pathlib import Path
from contextlib import closing
from unittest.mock import patch
import requests
from weex_isolated_pilot_offline_journal import reserve,connect
from weex_pilot_close_sdk_adapter import PilotCloseSDKAdapter
from weex_pilot_guarded_close_dispatch import dispatch_close

class Capture:
    count=0
    last=None
    def request(self,method,url,**kwargs):
        self.count+=1
        self.last={'method':method,'url':url,'payload':json.loads(kwargs['data']),
                   'hasSignedAuth':all(k in kwargs.get('headers',{}) for k in
                     ('ACCESS-KEY','ACCESS-SIGN','ACCESS-PASSPHRASE','ACCESS-TIMESTAMP'))}
        r=requests.Response()
        r.status_code=200
        r._content=b'{"success":true,"orderId":"FAKE_CAPTURED_ID"}'
        r.headers['Content-Type']='application/json'
        return r

def setup(root):
    (root/'weex_live_1x_pilot_config.json').write_text(json.dumps({
        'exchange':'WEEX','marginMode':'ISOLATED','leverage':1,'maxNewOrders':1,
        'executionEnabled':True,'liveOrderSubmissionAllowed':True,
        'requireExplicitTestOrderApproval':True,'reduceOnlyCloseVerified':True}))
    (root/'weex_credentials.json').write_text(json.dumps({
        'api_key':'TEST_ONLY','secret_key':'TEST_ONLY','passphrase':'TEST_ONLY'}))
    db=root/'pilot.sqlite3'
    reserve(db,pilot_id='P1',side='LONG',quantity='0.002',stop_price='2100')
    with closing(connect(db)) as c:
        cid,raw=c.execute('SELECT entry_id,proposals FROM pilot_v1').fetchone()
        c.execute("UPDATE pilot_v1 SET state='ENTRY_RECONCILED_EXTERNALLY'")
        c.commit()
    proposal={'prepared':True,'canSend':False,'payload':json.loads(raw)['close']}
    owned={'owned':True,'clientOrderId':cid,'quantity':'0.002','positionId':'P-1'}
    return db,proposal,owned

class Integrated(unittest.TestCase):
    def test_real_sdk_fake_network_one_shot(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);db,proposal,owned=setup(root);sink=Capture()
            transport=PilotCloseSDKAdapter(root,lambda op,p:True,lambda:sink)
            with patch('live_control.state',return_value={'mode':'STOPPED'}),patch('live_control.build_errors',return_value=[]):
                a=dispatch_close(db,'P1',proposal,ownership=owned,account_fresh=True,transport=transport)
                b=dispatch_close(db,'P1',proposal,ownership=owned,account_fresh=True,transport=transport)
            self.assertEqual(a['state'],'ACK_RECEIVED_UNRECONCILED',a)
            self.assertFalse(a['ordersConfirmed'])
            self.assertEqual(b['state'],'ALREADY_RESERVED_NO_RETRY')
            self.assertEqual(sink.count,1)
            self.assertEqual(sink.last['url'],'https://api-contract.weex.com/capi/v3/order')
            self.assertTrue(sink.last['payload']['reduceOnly'])
            self.assertEqual(sink.last['payload']['side'],'SELL')
            self.assertTrue(sink.last['hasSignedAuth'])
    def test_authorization_denied_before_network(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);db,proposal,owned=setup(root);sink=Capture()
            transport=PilotCloseSDKAdapter(root,lambda op,p:False,lambda:sink)
            with patch('live_control.state',return_value={'mode':'STOPPED'}),patch('live_control.build_errors',return_value=[]):
                r=dispatch_close(db,'P1',proposal,ownership=owned,account_fresh=True,transport=transport)
            self.assertEqual(r['state'],'OUTCOME_UNKNOWN')
            self.assertEqual(sink.count,0)
    def test_disabled_flag_denied(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);db,proposal,owned=setup(root);sink=Capture()
            cfg=root/'weex_live_1x_pilot_config.json'
            x=json.loads(cfg.read_text());x['liveOrderSubmissionAllowed']=False;cfg.write_text(json.dumps(x))
            transport=PilotCloseSDKAdapter(root,lambda op,p:True,lambda:sink)
            with patch('live_control.state',return_value={'mode':'STOPPED'}),patch('live_control.build_errors',return_value=[]):
                r=dispatch_close(db,'P1',proposal,ownership=owned,account_fresh=True,transport=transport)
            self.assertEqual(r['state'],'OUTCOME_UNKNOWN')
            self.assertEqual(sink.count,0)

if __name__=='__main__':unittest.main()
