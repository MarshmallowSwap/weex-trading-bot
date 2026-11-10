"""Verify production pilot SDK is disarmed without sending any network request."""
from pathlib import Path
from weex_pilot_emergency_close_sdk import PilotEmergencyCloseSDK,OP,exact_payload
class DenyNetwork:
 def request(self,*args,**kwargs):
  raise AssertionError('NETWORK_MUST_NEVER_BE_CALLED')
 def close(self):pass
pilot=PilotEmergencyCloseSDK(Path(__file__).resolve().parent,
  authorization=lambda op,p:True,session_factory=lambda:DenyNetwork())
try:
 pilot.send_emergency_close(OP,exact_payload('814587923356713162'))
except PermissionError as exc:
 assert str(exc)=='PILOT_EMERGENCY_CLOSE_NOT_ENABLED',str(exc)
 print('SDK_DISARMED_DENIED_BEFORE_NETWORK: PASS')
else:
 raise AssertionError('SDK_UNEXPECTEDLY_ACCEPTED_REAL_DISPATCH')
