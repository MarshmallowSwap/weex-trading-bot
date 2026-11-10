import json,tempfile,unittest
from pathlib import Path
from contextlib import closing
from unittest.mock import patch
import requests
from weex_isolated_pilot_offline_journal import reserve,connect
from weex_pilot_emergency_close_sdk import PilotEmergencyCloseSDK,exact_payload
from weex_pilot_emergency_dispatch import dispatch

class Capture:
    count=0;payload=None
    def request(self,method,url,**kwargs):
        self.count+=1
        self.payload=json.loads(kwargs['data'])
        assert method=='POST' and url=='https://api-contract.weex.com/capi/v3/closePositions'
        r=requests.Response();r.status_code=200
        r._content=b'[{"positionId":123456789,"success":true,"successOrderId":987654321}]'
        r.headers['Content-Type']='application/json'
        return r
def setup(root,enabled=True):
    (root/'weex_live_1x_pilot_config.json').write_text(json.dumps({
        'exchange':'WEEX','marginMode':'ISOLATED','leverage':1,'maxNewOrders':1,
        'executionEnabled':enabled,'liveOrderSubmissionAllowed':enabled,
        'requireExplicitTestOrderApproval':True}))
    (root/'weex_credentials.json').write_text(json.dumps({
        'api_key':'DUMMY','secret_key':'DUMMY','passphrase':'DUMMY'}))
    db=root/'pilot.sqlite3'
    reserve(db,pilot_id='P1',side='LONG',quantity='0.002',stop_price='2100')
    with closing(connect(db)) as c:
        entry=c.execute('SELECT entry_id FROM pilot_v1').fetchone()[0]
        c.execute("UPDATE pilot_v1 SET state='ENTRY_RECONCILED_EXTERNALLY'")
        c.commit()
    ownership={'owned':True,'clientOrderId':entry,'quantity':'0.002','positionId':'123456789'}
    pos={'symbol':'ETHUSDT','id':'123456789','marginType':'ISOLATED','side':'LONG','size':'0.002'}
    return db,ownership,pos
class Emergency(unittest.TestCase):
    def test_exact_position_sdk_and_no_repeat(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);db,owner,pos=setup(root);capture=Capture()
            transport=PilotEmergencyCloseSDK(root,lambda op,p:True,lambda:capture)
            with patch('live_control.state',return_value={'mode':'STOPPED'}),patch('live_control.build_errors',return_value=[]):
                result=dispatch(db,'P1',ownership=owner,observed_position=pos,transport=transport)
                second=dispatch(db,'P1',ownership=owner,observed_position=pos,transport=transport)
            self.assertEqual(result['state'],'ACK_RECEIVED_NEEDS_EXCHANGE_READBACK')
            self.assertFalse(result['verifiedFlat'])
            self.assertEqual(second['state'],'NO_RETRY_ALREADY_RESERVED')
            self.assertEqual(capture.count,1)
            self.assertEqual(capture.payload,{'symbol':'ETHUSDT','positionId':123456789})
    def test_disabled_refuses_network(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);db,owner,pos=setup(root,False);capture=Capture()
            transport=PilotEmergencyCloseSDK(root,lambda op,p:True,lambda:capture)
            with patch('live_control.state',return_value={'mode':'STOPPED'}),patch('live_control.build_errors',return_value=[]):
                result=dispatch(db,'P1',ownership=owner,observed_position=pos,transport=transport)
            self.assertEqual(result['state'],'OUTCOME_UNKNOWN')
            self.assertEqual(capture.count,0)
    def test_wrong_position_never_reserved(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);db,owner,pos=setup(root);capture=Capture()
            transport=PilotEmergencyCloseSDK(root,lambda op,p:True,lambda:capture)
            with self.assertRaises(PermissionError):
                dispatch(db,'P1',ownership=owner,observed_position={**pos,'id':'123456788'},transport=transport)
            self.assertEqual(capture.count,0)
    def test_symbol_only_or_blank_never_allowed(self):
        for pid in (None,'',0,-1,'1.5',True):
            with self.assertRaises(ValueError):exact_payload(pid)
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);setup(root);capture=Capture()
            transport=PilotEmergencyCloseSDK(root,lambda op,p:True,lambda:capture)
            with self.assertRaises(PermissionError):
                transport.send_emergency_close('post_capi_v3_closePositions',{'symbol':'ETHUSDT'})
            self.assertEqual(capture.count,0)
if __name__=='__main__':unittest.main()
