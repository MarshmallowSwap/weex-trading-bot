import tempfile, unittest
from pathlib import Path
from weex_trading_modes import (get_mode,set_mode,enqueue_manual,claim_next,finish_request,
    normalize_symbol,normalize_side,parse_manual_command,validate_entry_book)

class TradingModeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
    def tearDown(self): self.tmp.cleanup()
    def test_default_is_alerts_only(self):
        self.assertEqual(get_mode(self.root)['mode'],'alerts_only')
    def test_only_supported_modes(self):
        for mode in ('automatic','alerts_only','automatic_manual'):
            self.assertEqual(set_mode(self.root,mode,'test')['mode'],mode)
        with self.assertRaises(ValueError): set_mode(self.root,'live_now','test')
    def test_manual_requires_explicit_mode(self):
        with self.assertRaises(PermissionError): enqueue_manual(self.root,'SOL','LONG','user')
    def test_symbol_normalization(self):
        self.assertEqual(normalize_symbol(' sol '),'SOLUSDT')
        self.assertEqual(normalize_symbol('SOLUSDT'),'SOLUSDT')
        for bad in ('', 'BTC/USDT','SOL USDT','/start','BTCUSDT;DROP'):
            with self.assertRaises(ValueError): normalize_symbol(bad)
    def test_manual_command_requires_token_and_direction(self):
        self.assertEqual(parse_manual_command(' sol long '),('SOLUSDT','LONG'))
        self.assertEqual(parse_manual_command('SOLUSDT SHORT'),('SOLUSDT','SHORT'))
        self.assertIsNone(parse_manual_command('SOL'))
        self.assertIsNone(parse_manual_command('/start'))
        with self.assertRaisesRegex(ValueError,'MANUAL_DIRECTION_REQUIRED'):
            parse_manual_command('SOL BUY')
        with self.assertRaisesRegex(ValueError,'MANUAL_DIRECTION_REQUIRED'):
            normalize_side('BUY')
    def test_manual_signal_overrides_candidate_spread_and_depth_filters(self):
        book={'status':'OK','bestBid':'100','bestAsk':'101','spreadBps':99,
              'depthUnitVerified':False,'passed':False}
        self.assertEqual(validate_entry_book(book,manual_override=True),
                         {'bestBid':__import__('decimal').Decimal('100'),
                          'bestAsk':__import__('decimal').Decimal('101')})
        with self.assertRaisesRegex(ValueError,'LIVE_BOOK_UNVERIFIED'):
            validate_entry_book(book)
        with self.assertRaisesRegex(ValueError,'LIVE_ORDERBOOK_QUOTES_INVALID'):
            validate_entry_book({'status':'OK','bestBid':'0','bestAsk':'1'},manual_override=True)
    def test_queue_claim_and_finish(self):
        set_mode(self.root,'automatic_manual','test')
        req=enqueue_manual(self.root,'SOL','LONG','test',now=100)
        claimed=claim_next(self.root,now=110)
        self.assertEqual(claimed['id'],req['id'])
        self.assertEqual(claimed['side'],'LONG')
        self.assertEqual(claimed['state'],'PROCESSING')
        self.assertIsNone(claim_next(self.root,now=110))
        self.assertTrue(finish_request(self.root,req['id'],'REVIEW_REQUIRED',{'reason':'gate'}))
        self.assertFalse(finish_request(self.root,req['id'],'PROTECTED'))
    def test_duplicate_pending_symbol_blocked(self):
        set_mode(self.root,'automatic_manual','test')
        enqueue_manual(self.root,'SOL','LONG','test')
        with self.assertRaises(ValueError): enqueue_manual(self.root,'SOLUSDT','SHORT','test')
    def test_expired_manual_request_is_not_opened_later(self):
        set_mode(self.root,'automatic_manual','test')
        req=enqueue_manual(self.root,'SOL','LONG','test',now=100)
        self.assertIsNone(claim_next(self.root,request_id=req['id'],now=100+91))
        from weex_trading_modes import connect
        c=connect(self.root)
        try:state=c.execute('SELECT state,detail FROM manual_requests_v1 WHERE id=?',(req['id'],)).fetchone()
        finally:c.close()
        self.assertEqual(state['state'],'REJECTED')
        self.assertIn('MANUAL_REQUEST_EXPIRED',state['detail'])
    def test_switching_away_cancels_unclaimed_manual_requests(self):
        set_mode(self.root,'automatic_manual','test')
        req=enqueue_manual(self.root,'SOL','LONG','test')
        set_mode(self.root,'alerts_only','test')
        from weex_trading_modes import connect
        c=connect(self.root)
        try:state=c.execute('SELECT state FROM manual_requests_v1 WHERE id=?',(req['id'],)).fetchone()[0]
        finally:c.close()
        self.assertEqual(state,'REJECTED')
    def test_terminal_state_validation(self):
        set_mode(self.root,'automatic_manual','test')
        req=enqueue_manual(self.root,'ETH','SHORT','test')
        claim_next(self.root)
        with self.assertRaises(ValueError): finish_request(self.root,req['id'],'OPENED')
    def test_manual_telegram_position_is_managed_but_excluded_from_automatic_capacity(self):
        import json,sqlite3
        from weex_capacity import lifecycle_position_ids,account_capacity
        db=self.root/'lifecycle.sqlite3';c=sqlite3.connect(db)
        c.execute('CREATE TABLE trades_v1(id TEXT,state TEXT,owned TEXT,plan TEXT)')
        c.executemany('INSERT INTO trades_v1 VALUES(?,?,?,?)',[
            ('auto','PROTECTED',json.dumps({'positionId':'1','entrySource':'automatic'}),'{}'),
            ('manual','PROTECTED',json.dumps({'positionId':'2','entrySource':'manual_telegram'}),'{}')])
        c.commit();c.close()
        ids=lifecycle_position_ids(db)
        positions=[{'id':'1','symbol':'BTCUSDT'},{'id':'2','symbol':'SOLUSDT'}]
        capacity=account_capacity(positions,[],managed_position_ids=ids)
        self.assertEqual(ids,{'1'})
        self.assertEqual(capacity['positionCount'],1)
        self.assertEqual(capacity['manualPositionsExcluded'],1)
        self.assertEqual(capacity['count'],1)
if __name__=='__main__': unittest.main()
