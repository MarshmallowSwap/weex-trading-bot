"""Offline WEEX replacement request construction tests."""
import copy
import unittest
from weex_tp_repair_request import build
from weex_tp_repair_simulator import client_id

class ReplacementRequestTests(unittest.TestCase):
    def setUp(self):
        self.proposal={'eligible':True,'dispatchAllowed':False,'tradeId':'fake_ltc',
                       'symbol':'LTCUSDT','positionId':'p1'}
        self.trade={'id':'fake_ltc','symbol':'LTCUSDT',
                    'owned':{'positionId':'p1','quantity':'1','tpRequest':{
                        'symbol':'LTCUSDT','clientAlgoId':'original','planType':'TAKE_PROFIT',
                        'triggerPrice':'91','executePrice':'0','quantity':'1',
                        'positionSide':'LONG','triggerPriceType':'MARK_PRICE',
                        'reduceOnly':True,'closePosition':False}}}
    def test_fixed_request_serializes_offline(self):
        result=build(self.proposal,self.trade)
        self.assertEqual(result['request']['clientAlgoId'],client_id('fake_ltc','p1'))
        self.assertEqual(result['operation'],'post_capi_v3_placeTpSlOrder')
        self.assertEqual(result['sdkPreview']['networkRequests'],0)
        self.assertFalse(result['dispatchAllowed'])
    def test_original_payload_immutable(self):
        initial=copy.deepcopy(self.trade)
        build(self.proposal,self.trade)
        self.assertEqual(initial,self.trade)
    def test_mutated_quantity_rejected(self):
        self.trade['owned']['tpRequest']['quantity']='2'
        with self.assertRaises(ValueError):build(self.proposal,self.trade)
    def test_no_reduce_only_rejected(self):
        self.trade['owned']['tpRequest']['reduceOnly']=False
        with self.assertRaises(ValueError):build(self.proposal,self.trade)
    def test_wrong_position_rejected(self):
        self.proposal['positionId']='p2'
        with self.assertRaises(ValueError):build(self.proposal,self.trade)
    def test_wrong_symbol_rejected(self):
        self.trade['owned']['tpRequest']['symbol']='BTCUSDT'
        with self.assertRaises(ValueError):build(self.proposal,self.trade)
    def test_missing_guard_rejected(self):
        self.proposal['eligible']=False
        with self.assertRaises(ValueError):build(self.proposal,self.trade)
    def test_no_network_path(self):
        self.trade['owned']['tpOperation']='post_capi_v3_order'
        with self.assertRaises(ValueError):build(self.proposal,self.trade)

if __name__=='__main__':
    unittest.main()
