import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import requests
from weex_isolated_pilot_offline_journal import reserve
from weex_pilot_entry_sdk_adapter import PilotEntrySDKAdapter,validate_entry
from weex_pilot_guarded_entry_dispatch import send_entry_once

ACCOUNT={'fresh':True,'isolatedLeverage':1,'marginMode':'ISOLATED',
         'positions':[],'regularOrders':[],'conditionalOrders':[]}
class Sink:
    count=0;last=None
    def request(self,method,url,**kwargs):
        self.count+=1
        self.last={'method':method,'url':url,'data':json.loads(kwargs['data'])}
        r=requests.Response();r.status_code=200
        r._content=b'{"success":true,"orderId":"CAPTURED_ENTRY"}'
        r.headers['Content-Type']='application/json'
        return r
def prepare(root,enabled=True):
    (root/'weex_live_1x_pilot_config.json').write_text(json.dumps({
        'exchange':'WEEX','marginMode':'ISOLATED','leverage':1,'maxNewOrders':1,
        'maxAdditionalNotionalUSDT':'5','executionEnabled':enabled,
        'liveOrderSubmissionAllowed':enabled,
        'requireExplicitTestOrderApproval':True,'reduceOnlyCloseVerified':enabled}))
    (root/'weex_credentials.json').write_text(json.dumps({
        'api_key':'DUMMY','secret_key':'DUMMY','passphrase':'DUMMY'}))
    db=root/'p.sqlite3'
    reserve(db,pilot_id='P1',side='LONG',quantity='0.002',stop_price='2100')
    return db
class EntryIntegrated(unittest.TestCase):
    def test_sdk_entry_exactly_once_and_unconfirmed(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);db=prepare(root);sink=Sink()
            adapter=PilotEntrySDKAdapter(root,lambda op,p:True,lambda:sink)
            with patch('live_control.state',return_value={'mode':'STOPPED'}),patch('live_control.build_errors',return_value=[]):
                first=send_entry_once(db,'P1',ask='2247',account=ACCOUNT,transport=adapter)
                second=send_entry_once(db,'P1',ask='2247',account=ACCOUNT,transport=adapter)
            self.assertEqual(first['state'],'ACK_RECEIVED_UNRECONCILED')
            self.assertFalse(first['entryConfirmed'])
            self.assertEqual(second['state'],'ALREADY_RESERVED_NO_RETRY')
            self.assertEqual(sink.count,1)
            self.assertEqual(sink.last['url'],'https://api-contract.weex.com/capi/v3/order')
            self.assertEqual(sink.last['data']['side'],'BUY')
            self.assertNotIn('reduceOnly',sink.last['data'])
    def test_flag_denied_without_dispatch_reservation(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);db=prepare(root,enabled=False);sink=Sink()
            adapter=PilotEntrySDKAdapter(root,lambda op,p:True,lambda:sink)
            with patch('live_control.state',return_value={'mode':'STOPPED'}),patch('live_control.build_errors',return_value=[]):
                with self.assertRaises(PermissionError):
                    send_entry_once(db,'P1',ask='2247',account=ACCOUNT,transport=adapter)
            self.assertEqual(sink.count,0)
    def test_oversize_is_blocked(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);db=prepare(root);sink=Sink()
            adapter=PilotEntrySDKAdapter(root,lambda op,p:True,lambda:sink)
            with patch('live_control.state',return_value={'mode':'STOPPED'}),patch('live_control.build_errors',return_value=[]):
                with self.assertRaisesRegex(ValueError,'ABOVE_5'):
                    send_entry_once(db,'P1',ask='2700',account=ACCOUNT,transport=adapter)
            self.assertEqual(sink.count,0)
    def test_account_occupied_denied(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);db=prepare(root);sink=Sink()
            adapter=PilotEntrySDKAdapter(root,lambda op,p:True,lambda:sink)
            with patch('live_control.state',return_value={'mode':'STOPPED'}),patch('live_control.build_errors',return_value=[]):
                with self.assertRaises(PermissionError):
                    send_entry_once(db,'P1',ask='2247',account={**ACCOUNT,'positions':[{'symbol':'ETHUSDT'}]},transport=adapter)
            self.assertEqual(sink.count,0)
if __name__=='__main__':unittest.main()
