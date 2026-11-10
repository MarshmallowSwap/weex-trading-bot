import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from weex_pilot_close_sdk_adapter import PilotCloseSDKAdapter

P={'symbol':'ETHUSDT','side':'SELL','positionSide':'LONG','type':'MARKET',
   'quantity':'0.002','reduceOnly':True,'newClientOrderId':'wxpilot_testclose'}
class SDKClose(unittest.TestCase):
 def test_unapproved_pilot_cannot_send(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);(p/'weex_live_1x_pilot_config.json').write_text(json.dumps({
    'exchange':'WEEX','marginMode':'ISOLATED','leverage':1,'maxNewOrders':1,
    'executionEnabled':False,'liveOrderSubmissionAllowed':False,
    'requireExplicitTestOrderApproval':True,'reduceOnlyCloseVerified':False}))
   with self.assertRaisesRegex(PermissionError,'PILOT_LIVE_CLOSE_NOT_APPROVED'):
    PilotCloseSDKAdapter(p,lambda *_:True).send_close_only('post_capi_v3_order',P)
 def test_opening_order_denied(self):
  with tempfile.TemporaryDirectory() as t:
   with self.assertRaises(ValueError):
    PilotCloseSDKAdapter(t).send_close_only('post_capi_v3_order',{**P,'side':'BUY'})
 def test_other_operation_denied(self):
  with self.assertRaises(PermissionError):
   PilotCloseSDKAdapter('.').send_close_only('post_capi_v3_account_leverage',P)
 def test_no_constructor_submission(self):
  with tempfile.TemporaryDirectory() as t:
   PilotCloseSDKAdapter(t)
if __name__=='__main__':unittest.main()
