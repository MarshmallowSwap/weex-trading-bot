"""Regression: emergency exit and an active attached stop conflict, fail closed."""
import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from test_weex_pilot_emergency_attested_plan import fixtures,call
from weex_pilot_exit_conflict_audit import assess
class ExitConflict(unittest.TestCase):
 def test_emergency_refuses_position_with_active_stop(self):
  with tempfile.TemporaryDirectory() as t:
   db=Path(t)/'pilot.db';b,p,o,f=fixtures(db)
   stop={'symbol':'ETHUSDT','orderType':'STOP_MARKET','algoStatus':'UNTRIGGERED',
         'reduceOnly':True,'closePosition':True,'triggerPrice':'2100'}
   result=call(db,b,p,o,f,conditional_orders=[stop])
   self.assertFalse(result['prepared'])
   self.assertEqual(result['reason'],'NONEXCLUSIVE_POSITION_OR_OPEN_ORDERS')
 def test_readiness_audit_does_not_enable_orders(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t)
   (root/'weex_live_1x_pilot_config.json').write_text(json.dumps({
    'executionEnabled':False,'liveOrderSubmissionAllowed':False,
    'stopLossVerified':False,'reduceOnlyCloseVerified':False}))
   with patch('live_control.state',return_value={'mode':'STOPPED'}),patch(
       'live_control.build_errors',return_value=[]):
    a=assess(root)
   self.assertTrue(a['sdkPositionCloseSerializationVerified'])
   self.assertTrue(a['emergencyCloseRejectedWhileAttachedStopActive'])
   self.assertFalse(a['pilotReadyForRealEntry'])
   self.assertEqual(a['exchangeWrites'],0)
if __name__=='__main__':unittest.main()
