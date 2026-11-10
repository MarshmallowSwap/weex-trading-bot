import unittest
from weex_live_position_protection_shadow import assess
class CoverageTest(unittest.TestCase):
 def setUp(self):
  self.p=[{'id':1,'symbol':'TRUTHUSDT','side':'SHORT','size':'10'},
          {'id':2,'symbol':'UAIUSDT','side':'SHORT','size':'20'}]
  self.tp=[{'symbol':'TRUTHUSDT','side':'BUY','positionSide':'SHORT',
     'orderType':'TAKE_PROFIT_MARKET','algoStatus':'UNTRIGGERED',
     'reduceOnly':True,'quantity':'10','triggerPrice':'1',
     'closePosition':False,'workingType':'CONTRACT_PRICE'}]
 def test_real_account_scenario_does_not_allow_entries(self):
  r=assess(self.p,[],self.tp)
  self.assertEqual(r['unprotectedCount'],2)
  self.assertFalse(r['newEntriesAllowed'])
  self.assertFalse(r['rows'][1]['fullTpObserved'])
 def test_no_snapshot_is_invalid(self):
  self.assertEqual(assess(None,[],[])['status'],'SNAPSHOT_INVALID')
 def test_empty_snapshot_not_trading_authorization(self):
  self.assertFalse(assess([],[],[])['newEntriesAllowed'])
 def test_stop_for_other_symbol_not_coverage(self):
  stop={'symbol':'ETHUSDT','positionSide':'SHORT','orderType':'STOP_MARKET',
    'algoStatus':'UNTRIGGERED','reduceOnly':True,'quantity':'10'}
  self.assertEqual(assess(self.p,[],self.tp+[stop])['unprotectedCount'],2)
 def test_stop_wrong_quantity_not_full_coverage(self):
  stop={'symbol':'TRUTHUSDT','positionSide':'SHORT','orderType':'STOP_MARKET',
    'algoStatus':'UNTRIGGERED','reduceOnly':True,'quantity':'5'}
  self.assertFalse(assess(self.p,[],self.tp+[stop])['rows'][0]['fullStopObserved'])
 def test_stop_matching_quantity_identified_but_not_ownership(self):
  stop={'symbol':'TRUTHUSDT','positionSide':'SHORT','side':'BUY',
    'orderType':'STOP_MARKET','triggerPrice':'2','algoStatus':'UNTRIGGERED',
    'reduceOnly':True,'quantity':'10.000'}
  r=assess(self.p,[],self.tp+[stop])
  self.assertTrue(r['rows'][0]['fullStopObserved'])
  self.assertFalse(r['rows'][0]['botOwnershipVerified'])
 def test_stop_not_reduce_only_rejected(self):
  stop={'symbol':'TRUTHUSDT','positionSide':'SHORT','orderType':'STOP_MARKET',
    'algoStatus':'UNTRIGGERED','reduceOnly':False,'quantity':'10'}
  self.assertFalse(assess(self.p,[],self.tp+[stop])['rows'][0]['fullStopObserved'])
 def test_invalid_position_identity_blocks(self):
  self.assertEqual(assess([{'symbol':'BTCUSDT','side':'UNKNOWN'}],[],[])['status'],
                   'POSITION_IDENTITY_UNKNOWN')
if __name__=='__main__':unittest.main()
