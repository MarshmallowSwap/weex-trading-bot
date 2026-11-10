import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from weex_eth_50x_protected_preflight import scoped_preview
from test_weex_pretrade_regression import META

class Scoped50Pilot(unittest.TestCase):
 def setUp(self):
  self.d=tempfile.TemporaryDirectory();self.addCleanup(self.d.cleanup)
  self.r=Path(self.d.name)
  (self.r/'weex_ai_risk_config.json').write_text(json.dumps({
   'execution':{'enabled':False,'mode':'PRETRADE'},
   'risk':{'minimumLeverage':50}}))
  self.meta={**META,'symbol':'ETHUSDT','maxLeverage':400,'minOrderSize':'0.001'}
  self.br=[{'notionalFloor':'0','notionalCap':'1000','initialLeverage':400}]
  self.book={'symbol':'ETHUSDT','status':'OK','depthUnitVerified':True,
    'bestBid':'2120.32','bestAsk':'2120.33'}
  self.config=[{'symbol':'ETHUSDT','marginType':'CROSSED',
    'separatedType':'COMBINED','crossLeverage':'1'}]
 def go(self):
  with patch('live_control.state',return_value={'mode':'STOPPED'}):
   return scoped_preview(self.meta,self.br,self.book,self.config,root=self.r)
 def test_minimum_quantity_50x_not_maximum_contract_leverage(self):
  x=self.go()
  self.assertEqual(x['quantity'],'0.001')
  self.assertEqual(x['leverage'],'50')
  self.assertEqual(x['notionalUSDT'],'2.12033')
  self.assertEqual(x['indicativeInitialMarginUSDT'],'0.0424066')
  self.assertTrue(x['leverageSetupRequired'])
  self.assertEqual(x['ordersSent'],0)
  self.assertFalse(x['maxLossGuaranteed'])
 def test_reject_stale_or_unverified_book(self):
  self.book['depthUnitVerified']=False
  with self.assertRaisesRegex(ValueError,'LIVE_BOOK_NOT_CERTIFIED'):self.go()
 def test_minimum_cost_above_5_is_blocked(self):
  self.meta['minOrderSize']='0.01'
  with self.assertRaisesRegex(ValueError,'NOTIONAL_CAP'):self.go()
 def test_contract_risk_tier_below_50_fails(self):
  self.br[0]['initialLeverage']=49
  with self.assertRaisesRegex(ValueError,'RISK_BRACKET'):self.go()
 def test_wrong_margin_mode_rejected(self):
  self.config[0]['marginType']='ISOLATED'
  with self.assertRaisesRegex(ValueError,'CROSS_HEDGE'):self.go()
 def test_executing_bot_cannot_do_pilot(self):
  with patch('live_control.state',return_value={'mode':'RUNNING'}):
   with self.assertRaisesRegex(PermissionError,'MUST_STAY_STOPPED'):
    scoped_preview(self.meta,self.br,self.book,self.config,root=self.r)
 def test_pilot_fails_if_execution_flag_on(self):
  p=self.r/'weex_ai_risk_config.json'
  x=json.loads(p.read_text());x['execution']['enabled']=True;p.write_text(json.dumps(x))
  with self.assertRaisesRegex(PermissionError,'MUST_BE_DISABLED'):self.go()
 def test_account_leverage_50_removes_setup_requirement(self):
  self.config[0]['crossLeverage']='50'
  self.assertFalse(self.go()['leverageSetupRequired'])
if __name__=='__main__':unittest.main()
