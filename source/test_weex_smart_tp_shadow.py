"""No-network Smart TP shadow decision tests."""
import unittest
from weex_smart_tp_shadow import evaluate, advance_trailing

class ShadowTests(unittest.TestCase):
    def setUp(self):
        self.p={'side':'LONG','quantity':'26.5','entryPrice':'195.26','entryFeeUSDT':'4.14'}
        self.m={'markPrice':'198','atr':'0.35','adx':'32','volumeRatio':'1.4',
                'strengthScore':'80','observedAtMs':100000}
        self.s={'tpMode':'adaptive_shadow','exitFeeRate':'0.0008','targetNetProfitUSDT':'15'}
    def run_case(self):return evaluate(self.p,self.m,self.s,now_ms=100010)
    def test_strong_trend_suggests_trailing_only(self):
        r=self.run_case()
        self.assertEqual(r['decision'],'TRAILING_CANDIDATE')
        self.assertFalse(r['dispatchAllowed'])
        self.assertFalse(r['stopIsActiveOnExchange'])
    def test_weak_trend_fixed_exit_candidate(self):
        self.m.update(strengthScore='10',adx='12',volumeRatio='0.1')
        self.assertEqual(self.run_case()['decision'],'FIXED_EXIT_CANDIDATE')
    def test_under_target_wait(self):
        self.m['markPrice']='195.30'
        self.assertEqual(self.run_case()['decision'],'WAIT')
    def test_stale_market_blocks(self):
        self.m['observedAtMs']=100
        self.assertEqual(self.run_case()['decision'],'BLOCK')
    def test_nan_rejected(self):
        self.m['atr']='NaN'
        self.assertEqual(self.run_case()['decision'],'BLOCK')
    def test_negative_fee_rejected(self):
        self.p['entryFeeUSDT']='-1'
        self.assertEqual(self.run_case()['decision'],'BLOCK')
    def test_short_works(self):
        self.p.update(side='SHORT',entryPrice='200')
        r=self.run_case()
        self.assertEqual(r['decision'],'TRAILING_CANDIDATE')
        self.assertGreater(float(r['proposedStopPrice']),float(self.m['markPrice']))
    def test_mode_isolation(self):
        self.s['tpMode']='fixed'
        self.assertEqual(self.run_case()['reason'],'MODE_NOT_ADAPTIVE_SHADOW')
    def test_long_stop_never_moves_down(self):
        first=advance_trailing(None,side='LONG',mark_price=198,atr='.3',multiplier=2)
        next_=advance_trailing(first,side='LONG',mark_price=200,atr='.4',multiplier=2)
        down=advance_trailing(next_,side='LONG',mark_price=199,atr='1.0',multiplier=2)
        self.assertGreater(float(next_['stopPrice']),float(first['stopPrice']))
        self.assertEqual(down['stopPrice'],next_['stopPrice'])
    def test_short_stop_never_moves_up(self):
        first=advance_trailing(None,side='SHORT',mark_price=198,atr='.3',multiplier=2)
        next_=advance_trailing(first,side='SHORT',mark_price=196,atr='.4',multiplier=2)
        up=advance_trailing(next_,side='SHORT',mark_price=197,atr='1',multiplier=2)
        self.assertLess(float(next_['stopPrice']),float(first['stopPrice']))
        self.assertEqual(up['stopPrice'],next_['stopPrice'])
    def test_cross_side_state_blocks(self):
        first=advance_trailing(None,side='LONG',mark_price=198,atr='.3',multiplier=2)
        with self.assertRaises(ValueError):
            advance_trailing(first,side='SHORT',mark_price=197,atr='.3',multiplier=2)
    def test_invalid_quantity_blocks(self):
        self.p['quantity']='0'
        self.assertEqual(self.run_case()['decision'],'BLOCK')

if __name__=='__main__':
    unittest.main()
