import unittest
from weex_cross_1x_pilot_exchange_preflight import check
CFG={'exchange':'WEEX','marginMode':'CROSS','leverage':1,
     'executionEnabled':False,'liveOrderSubmissionAllowed':False}
EX={'symbol':'ETHUSDT','marginType':'CROSS','crossLeverage':'1'}
class CrossPilot(unittest.TestCase):
 def check(self,conf=None,exchange=None,positions=None,regular=None,algos=None):
  return check(conf or CFG,exchange or EX,positions if positions is not None else [],
      regular if regular is not None else [],algos if algos is not None else [],
      'STOPPED',[])
 def test_cross_1x_flat_ready_but_no_order_auth(self):
  r=self.check();self.assertTrue(r['crossExchangeReady']);self.assertFalse(r['entryAuthorized'])
 def test_isolated_exchange_rejected(self):
  self.assertIn('EXCHANGE_ETH_NOT_CROSS',
       self.check(exchange={**EX,'marginType':'ISOLATED'})['reasons'])
 def test_400x_cross_rejected(self):
  self.assertIn('EXCHANGE_CROSS_LEVERAGE_NOT_1X',
       self.check(exchange={**EX,'crossLeverage':'400'})['reasons'])
 def test_position_rejected(self):
  self.assertFalse(self.check(positions=[{'symbol':'ETHUSDT'}])['crossExchangeReady'])
 def test_order_rejected(self):
  self.assertFalse(self.check(regular=[{'symbol':'ETHUSDT'}])['crossExchangeReady'])
 def test_active_pilot_rejected(self):
  self.assertFalse(self.check(conf={**CFG,'executionEnabled':True})['crossExchangeReady'])
 def test_isolated_pilot_config_rejected(self):
  self.assertFalse(self.check(conf={**CFG,'marginMode':'ISOLATED'})['crossExchangeReady'])
if __name__=='__main__':unittest.main()
