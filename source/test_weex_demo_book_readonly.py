import copy,unittest
from datetime import datetime,timezone
from weex_demo_book_readonly import inspect_snapshot,assess,display_decimal
class DemoBookTests(unittest.TestCase):
    def setUp(self):
        header='1 heading WLDSUSDT Perp Demo, Value: 1\n2 container depth-list-container\n3 container depth-list-header\n4 text Price\n5 container\n6 text ( SUSDT )\n7 text Amount\n8 text (SUSDT)\n9 text Sum\n10 text (SUSDT)\n'
        rows=''
        for i in range(10,25):rows+=f'11 container ask-contract-{i}\n12 text {1.001+(24-i)*.001:.3f}\n13 text 2.00K\n14 text 3K\n'
        for i in range(15):rows+=f'11 container bid-contract-{i}\n12 text {1-i*.001:.3f}\n13 text 2.00K\n14 text 3K\n'
        self.s={'url':'https://www.weex.com/futures/demo-trading/WLD-SUSDT','captureStartedAtMs':100000,'observedAtMs':101000,'ax':header+rows}
        self.market={'symbol':'WLDUSDT','marketSignal':'SHORT','checkedAt':datetime.fromtimestamp(100,timezone.utc).isoformat(),'momentum':{'confirmed':True},'trend':{'aligned':True}}
    def inspect(self):return inspect_snapshot(self.s,'WLD',now_ms=102000)
    def test_quote_amount_not_multiplied_and_rounding_is_conservative(self):
        b=self.inspect();self.assertTrue(b['passed']);self.assertEqual(b['top15BidNotionalLowerBound'],'29850.00');self.assertFalse(b['orderPermitted'])
    def test_grouped_prices_parsed_without_changing_magnitude(self):
        from decimal import Decimal
        self.assertEqual(display_decimal('2,397.03'),Decimal('2397.03'))
        for malformed in ('2,39.03','2.397,03','NaN','-1','1,23,456'):
            with self.assertRaises(ValueError):display_decimal(malformed)
    def test_live_wrong_symbol_and_host_are_rejected(self):
        for url in ('https://www.weex.com/futures/WLD-USDT','https://www.weex.com/futures/demo-trading/ETH-SUSDT','https://other.test/futures/demo-trading/WLD-SUSDT'):
            self.s['url']=url
            with self.assertRaises(ValueError):self.inspect()
    def test_wrong_unit_is_rejected(self):
        self.s['ax']=self.s['ax'].replace('(SUSDT)','(WLD)')
        with self.assertRaises(ValueError):self.inspect()
    def test_stale_future_slow_capture_are_rejected(self):
        for start,end in ((1000,2000),(103000,104000),(95000,101000),(101000,103000)):
            self.s.update(captureStartedAtMs=start,observedAtMs=end)
            with self.assertRaises(ValueError):self.inspect()
    def test_missing_row_duplicate_price_and_crossed_book_rejected(self):
        original=self.s['ax']
        for ax in (original.replace('bid-contract-14','bid-contract-15'),original.replace('text 0.999','text 1.000'),original.replace('text 1.001','text 1.000')):
            self.s['ax']=ax
            with self.assertRaises(ValueError):self.inspect()
    def test_low_depth_veto(self):
        self.s['ax']=self.s['ax'].replace('2.00K','1.00')
        self.assertIn('INSUFFICIENT_BOOK_DEPTH',self.inspect()['vetoReasons'])
    def test_wide_spread_veto(self):
        self.s['ax']=self.s['ax'].replace('text 1.001','text 1.0019')
        self.assertIn('SPREAD_TOO_WIDE',self.inspect()['vetoReasons'])
    def test_signal_gate_never_grants_execution(self):
        r=assess(self.s,'WLD',self.market,now_ms=102000)
        self.assertEqual(r['marketEligibility'],'DEMO_MARKET_CANDIDATE');self.assertFalse(r['orderPermitted'])
        self.market['marketSignal']='WAIT';self.market['momentum']['confirmed']=False
        r=assess(self.s,'WLD',self.market,now_ms=102000)
        self.assertEqual(r['marketEligibility'],'WAIT')
    def test_stale_or_other_symbol_signal_rejected(self):
        for field,value in (('symbol','ETHUSDT'),('checkedAt','1970-01-01T00:00:00+00:00')):
            m=copy.deepcopy(self.market);m[field]=value
            with self.assertRaises(ValueError):assess(self.s,'WLD',m,now_ms=102000)
if __name__=='__main__':unittest.main()
