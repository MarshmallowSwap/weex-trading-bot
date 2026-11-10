"""Offline WEEX net-limit shadow verification; no exchange requests."""
import unittest
from decimal import Decimal
from weex_tp_limit_shadow import propose,reconcile_fills

BASE=dict(trade_id='wxentry_example123',symbol='LTCUSDT',position_id='p1',
          side='LONG',quantity='94.6',entry_cost_usdt='5176.461',
          entry_fees_usdt='4.1411688',exit_fee_rate='.0008',
          target_net_usdt='15',price_tick='.01',
          position_observation={'id':'p1','symbol':'LTCUSDT','side':'LONG',
                                'size':'94.6','openValue':'5176.461','openFee':'4.1411688'},
          regular_orders=[],conditional_orders=[])

class LimitTests(unittest.TestCase):
    def test_long_15_net_is_limit_and_offline(self):
        p=propose(**BASE);r=p['request']
        self.assertEqual(r['price'],'54.97')
        self.assertEqual(r['type'],'LIMIT')
        self.assertEqual(r['timeInForce'],'GTC')
        self.assertEqual(r['side'],'SELL')
        self.assertTrue(r['reduceOnly'])
        self.assertFalse(p['dispatchAllowed'])
        self.assertEqual(p['sdkPreview']['networkRequests'],0)
        self.assertGreaterEqual(Decimal(p['estimatedNetAtLimitUSDT']),15)
    def test_short_side_and_limit(self):
        b={**BASE,'side':'SHORT','entry_cost_usdt':'5200'}
        b['position_observation']={**BASE['position_observation'],'side':'SHORT','openValue':'5200'}
        r=propose(**b)['request']
        self.assertEqual(r['side'],'BUY')
        self.assertEqual(r['positionSide'],'SHORT')
    def test_existing_tp_blocks(self):
        with self.assertRaisesRegex(ValueError,'EXISTING_SYMBOL_ORDER'):
            propose(**{**BASE,'conditional_orders':[{'symbol':'LTCUSDT'}]})
    def test_other_position_blocks(self):
        with self.assertRaisesRegex(ValueError,'POSITION_OWNERSHIP'):
            propose(**{**BASE,'position_observation':{**BASE['position_observation'],'id':'other'}})
    def test_changed_cost_blocks(self):
        with self.assertRaisesRegex(ValueError,'POSITION_OWNERSHIP'):
            propose(**{**BASE,'position_observation':{**BASE['position_observation'],'openValue':'5176.46'}})
    def test_malformed_quantity_blocks(self):
        with self.assertRaises(ValueError):
            propose(**{**BASE,'quantity':'NaN'})
    def test_open_unfilled(self):
        v=reconcile_fills(order_id='a',side='LONG',entry_quantity='2',
            entry_cost_usdt='200',entry_fees_usdt='.16',exit_fills=[],
            remaining_position_quantity='2')
        self.assertEqual(v['status'],'OPEN_UNFILLED')
    def test_partial_fill_tracks_remaining(self):
        v=reconcile_fills(order_id='a',side='LONG',entry_quantity='2',
            entry_cost_usdt='200',entry_fees_usdt='.16',
            exit_fills=[{'id':'f1','orderId':'a','side':'SELL','positionSide':'LONG',
                         'qty':'1','price':'105','commission':'.084','commissionAsset':'USDT'}],
            remaining_position_quantity='1')
        self.assertEqual(v['status'],'PARTIALLY_FILLED')
        self.assertEqual(Decimal(v['netRealizedBeforeFundingUSDT']),Decimal('4.836'))
    def test_full_fill(self):
        f=[{'id':'f1','orderId':'a','side':'BUY','positionSide':'SHORT',
            'qty':'2','price':'90','commission':'.144','commissionAsset':'USDT'}]
        v=reconcile_fills(order_id='a',side='SHORT',entry_quantity='2',
            entry_cost_usdt='200',entry_fees_usdt='.16',exit_fills=f,
            remaining_position_quantity='0')
        self.assertEqual(v['status'],'CLOSED_VERIFIED')
        self.assertEqual(Decimal(v['netRealizedBeforeFundingUSDT']),Decimal('19.696'))
    def test_unbound_fill_rejected(self):
        f=[{'id':'f1','orderId':'bad','side':'SELL','positionSide':'LONG',
            'qty':'2','price':'105','commission':'.16','commissionAsset':'USDT'}]
        with self.assertRaisesRegex(ValueError,'EXIT_FILL_NOT_BOUND'):
            reconcile_fills(order_id='a',side='LONG',entry_quantity='2',
                entry_cost_usdt='200',entry_fees_usdt='.16',exit_fills=f,
                remaining_position_quantity='0')
    def test_duplicate_fills_rejected(self):
        f={'id':'f1','orderId':'a','side':'SELL','positionSide':'LONG',
            'qty':'1','price':'105','commission':'.08','commissionAsset':'USDT'}
        with self.assertRaisesRegex(ValueError,'DUPLICATE'):
            reconcile_fills(order_id='a',side='LONG',entry_quantity='2',
                entry_cost_usdt='200',entry_fees_usdt='.16',exit_fills=[f,f],
                remaining_position_quantity='0')
    def test_wrong_remaining_rejected(self):
        with self.assertRaisesRegex(ValueError,'EXIT_QUANTITY'):
            reconcile_fills(order_id='a',side='LONG',entry_quantity='2',
                entry_cost_usdt='200',entry_fees_usdt='.16',exit_fills=[],
                remaining_position_quantity='1')
if __name__=='__main__':unittest.main()
