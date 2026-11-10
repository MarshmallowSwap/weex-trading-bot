import unittest
from decimal import Decimal
from weex_tp_pnl_preview import preview

class PnlPreviewTests(unittest.TestCase):
    def test_qnt_historical_position(self):
        p=preview(side='LONG',quantity='26.5',entry_cost_usdt='5174.415',
                  entry_fees_usdt='4.139532',exit_fee_rate='.0008',
                  target_net_usdt='15',price_tick='.01')
        self.assertEqual(p['triggerPrice'],'196.15')
        self.assertGreaterEqual(Decimal(p['estimatedNetAtTriggerUSDT']),Decimal('15'))
        self.assertFalse(p['dispatchAllowed'])
    def test_ltc_historical_position(self):
        p=preview(side='LONG',quantity='94.6',entry_cost_usdt='5176.461',
                  entry_fees_usdt='4.1411688',exit_fee_rate='.0008',
                  target_net_usdt='15',price_tick='.01')
        self.assertEqual(p['triggerPrice'],'54.97')
    def test_short_round_down(self):
        p=preview(side='SHORT',quantity='2',entry_cost_usdt='200',
                  entry_fees_usdt='.16',exit_fee_rate='.0008',
                  target_net_usdt='5',price_tick='.01')
        self.assertGreaterEqual(Decimal(p['estimatedNetAtTriggerUSDT']),Decimal('5'))
    def test_no_negative_fee(self):
        with self.assertRaises(ValueError):
            preview(side='LONG',quantity='1',entry_cost_usdt='100',
                    entry_fees_usdt='-1',exit_fee_rate='.0008',
                    target_net_usdt='15',price_tick='.01')
    def test_no_nan(self):
        with self.assertRaises(ValueError):
            preview(side='LONG',quantity='NaN',entry_cost_usdt='100',
                    entry_fees_usdt='1',exit_fee_rate='.0008',
                    target_net_usdt='15',price_tick='.01')
if __name__=='__main__':unittest.main()
