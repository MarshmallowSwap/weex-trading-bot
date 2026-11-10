"""Pure offline tests for the WEEX TP repair approval gate."""
import copy
import unittest
from weex_tp_repair_gate import evaluate

def fixture():
    trade={'id':'fake_ltc','symbol':'LTCUSDT','state':'REVIEW_REQUIRED',
           'plan':{'entrySource':'automatic'},
           'owned':{'entrySource':'automatic','positionId':'p1','entryOrderId':'e1',
                    'quantity':'1','actualEntryCostUSDT':'90','actualEntryFeesUSDT':'0.01',
                    'tpRequest':{'positionSide':'LONG','clientAlgoId':'original_tp'}}}
    writes={'ENTRY':{'response':{'success':True,'orderId':'e1'}},
            'TP':{'state':'RESPONSE_RECEIVED','response':[{'success':True,'orderId':'t1'}]}}
    positions=[{'id':'p1','symbol':'LTCUSDT','side':'LONG','size':'1',
                'openValue':'90','openFee':'0.01'}]
    history=[{'symbol':'LTCUSDT','algoId':'t1','clientAlgoId':'original_tp',
              'algoStatus':'CANCELED','actualOrderId':None}]
    return trade,writes,positions,[],[],history

class RepairGateTests(unittest.TestCase):
    def gate(self, modify=None, complete_history=True):
        data=list(copy.deepcopy(fixture()))
        if modify: modify(data)
        return evaluate(*data,complete_history=complete_history)
    def test_cancelled_eligible_for_proposal_only(self):
        x=self.gate()
        self.assertTrue(x['eligible'])
        self.assertFalse(x['dispatchAllowed'])
    def test_history_not_complete(self):
        self.assertEqual(self.gate(complete_history=False)['reason'],'INCOMPLETE_HISTORY')
    def test_active_tp_blocks(self):
        self.assertEqual(self.gate(lambda d:d[4].append({'symbol':'LTCUSDT'}))['reason'],'ALGO_ORDER_PRESENT')
    def test_regular_order_blocks(self):
        self.assertEqual(self.gate(lambda d:d[3].append({'symbol':'LTCUSDT'}))['reason'],'REGULAR_ORDERS_PRESENT')
    def test_filled_history_blocks(self):
        self.assertEqual(self.gate(lambda d:d[5][0].update(algoStatus='FILLED'))['reason'],'HISTORY_NOT_PROVEN_CANCELLED')
    def test_unknown_history_blocks(self):
        self.assertEqual(self.gate(lambda d:d[5][0].update(algoStatus='UNKNOWN'))['reason'],'HISTORY_NOT_PROVEN_CANCELLED')
    def test_exit_order_link_blocks(self):
        self.assertEqual(self.gate(lambda d:d[5][0].update(actualOrderId='exit1'))['reason'],'PRIOR_EXIT_EXECUTION_LINK')
    def test_position_changed_blocks(self):
        self.assertEqual(self.gate(lambda d:d[2][0].update(size='0.5'))['reason'],'POSITION_ECONOMICS_CHANGED')
    def test_ownership_unknown_blocks(self):
        self.assertEqual(self.gate(lambda d:d[0]['owned'].update(entryOrderId='wrong'))['reason'],'ENTRY_PROOF_MISSING')
    def test_manual_trade_blocks(self):
        self.assertEqual(self.gate(lambda d:d[0]['owned'].update(entrySource='manual_telegram'))['reason'],'NOT_AUTOMATIC_BOT_POSITION')
    def test_uncertain_previous_dispatch_blocks(self):
        self.assertEqual(self.gate(lambda d:d[1]['TP'].update(state='UNKNOWN'))['reason'],'TP_DISPATCH_UNCERTAIN')
    def test_duplicate_history_blocks(self):
        self.assertEqual(self.gate(lambda d:d[5].append(dict(d[5][0],algoId='t2')))['reason'],'ORIGINAL_TP_NOT_UNIQUE')
    def test_old_tp_ack_mismatch_blocks(self):
        self.assertEqual(self.gate(lambda d:d[1]['TP'].update(response=[{'success':True,'orderId':'different'}]))['reason'],'ORIGINAL_TP_ACK_MISMATCH')
    def test_old_tp_rejected_ack_blocks(self):
        self.assertEqual(self.gate(lambda d:d[1]['TP'].update(response=[{'success':False,'orderId':'t1'}]))['reason'],'ORIGINAL_TP_ACK_MISMATCH')
    def test_old_tp_absent_ack_blocks(self):
        self.assertEqual(self.gate(lambda d:d[1]['TP'].update(response=None))['reason'],'ORIGINAL_TP_ACK_MISMATCH')
    def test_no_prior_history_blocks(self):
        self.assertEqual(self.gate(lambda d:d[5].clear())['reason'],'MISSING_HISTORY_OF_PROTECTION')

if __name__ == '__main__':
    unittest.main()
