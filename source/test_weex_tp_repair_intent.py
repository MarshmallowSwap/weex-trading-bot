"""Isolated durable TP intent tests: no network or live order."""
import tempfile
import unittest
from pathlib import Path
from weex_tp_repair_journal import record
from weex_tp_repair_intent import prepare,get
from weex_tp_repair_request import build
from weex_live_worker import Gateway
from weex_tp_repair_transitions import mark_dispatch_unknown, reconcile

class IntentTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.proposal={'eligible':True,'dispatchAllowed':False,'tradeId':'fake_ltc',
                       'symbol':'LTCUSDT','positionId':'p1',
                       'reason':'CANCELLED_TP_CONFIRMED_PROPOSAL_ONLY'}
        self.trade={'id':'fake_ltc','symbol':'LTCUSDT','owned':{
            'positionId':'p1','quantity':'1','tpRequest':{
                'symbol':'LTCUSDT','clientAlgoId':'old','planType':'TAKE_PROFIT',
                'triggerPrice':'92','executePrice':'0','quantity':'1',
                'positionSide':'LONG','triggerPriceType':'MARK_PRICE',
                'reduceOnly':True,'closePosition':False}}}
    def test_requires_persisted_proposal(self):
        with self.assertRaisesRegex(ValueError,'PERSISTED_PROPOSAL_REQUIRED'):
            prepare(self.root,self.proposal,self.trade)
    def test_durable_intent_survives_reopen(self):
        record(self.root,self.proposal)
        first=prepare(self.root,self.proposal,self.trade)
        self.assertEqual(first['state'],'PREPARED_NOT_SENT')
        self.assertEqual(first['networkRequests'],0)
        second=prepare(self.root,self.proposal,self.trade)
        self.assertEqual(second['state'],'PREPARED_NOT_SENT')
        self.assertEqual(get(self.root,'fake_ltc')['payloadSha256'],first['payloadSha256'])
        self.assertFalse(second['dispatchAllowed'])
    def test_changed_payload_is_rejected(self):
        record(self.root,self.proposal)
        prepare(self.root,self.proposal,self.trade)
        self.trade['owned']['tpRequest']['triggerPrice']='93'
        with self.assertRaisesRegex(ValueError,'IMMUTABLE_REPAIR_INTENT_CONFLICT'):
            prepare(self.root,self.proposal,self.trade)
    def test_gateway_preview_exact_persisted_payload(self):
        record(self.root,self.proposal)
        prepare(self.root,self.proposal,self.trade)
        expected=build(self.proposal,self.trade)
        gateway=Gateway(self.root,None)
        result=gateway.repair_preview('fake_ltc',expected['operation'],expected['request'])
        self.assertEqual(result['state'],'VALIDATED_NOT_SUBMITTED')
        self.assertFalse(result['dispatchAllowed'])
    def test_gateway_preview_changed_payload_blocks(self):
        record(self.root,self.proposal)
        prepare(self.root,self.proposal,self.trade)
        expected=build(self.proposal,self.trade)
        with self.assertRaises(PermissionError):
            Gateway(self.root,None).repair_preview('fake_ltc',expected['operation'],
                dict(expected['request'],quantity='2'))
    def test_dispatch_transition_is_single_use(self):
        record(self.root,self.proposal)
        saved=prepare(self.root,self.proposal,self.trade)
        first=mark_dispatch_unknown(self.root,'fake_ltc',expected_digest=saved['payloadSha256'])
        second=mark_dispatch_unknown(self.root,'fake_ltc',expected_digest=saved['payloadSha256'])
        self.assertEqual(first['state'],'UNKNOWN')
        self.assertEqual(second['state'],'NO_RETRY')
    def test_wrong_digest_cannot_dispatch(self):
        record(self.root,self.proposal)
        prepare(self.root,self.proposal,self.trade)
        with self.assertRaises(PermissionError):
            mark_dispatch_unknown(self.root,'fake_ltc',expected_digest='incorrect')
    def test_uncertain_without_exchange_evidence(self):
        record(self.root,self.proposal)
        saved=prepare(self.root,self.proposal,self.trade)
        mark_dispatch_unknown(self.root,'fake_ltc',expected_digest=saved['payloadSha256'])
        request=build(self.proposal,self.trade)['request']
        result=reconcile(self.root,'fake_ltc',{'complete':False},position_id='p1',
                         client_algo_id=request['clientAlgoId'])
        self.assertEqual(result['state'],'RECONCILIATION_REQUIRED')
    def test_other_position_is_rejected(self):
        record(self.root,self.proposal)
        self.trade['owned']['positionId']='different'
        with self.assertRaises(ValueError):
            prepare(self.root,self.proposal,self.trade)

if __name__=='__main__':
    unittest.main()
