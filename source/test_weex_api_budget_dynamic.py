import tempfile,unittest
from email.utils import formatdate
from pathlib import Path
from weex_api_budget import Budget,BudgetDeferred

class Clock:
    def __init__(self):self.t=100000
    def __call__(self):return self.t

class DynamicBudgetTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.clock=Clock();self.b=Budget(Path(self.tmp.name),self.clock)
        self.b.install_rate_limits([
            {'rateLimitType':'REQUEST_WEIGHT','interval':'MINUTE','intervalNum':10,'limit':500},
            {'rateLimitType':'ORDERS','interval':'MINUTE','intervalNum':1,'limit':300}])
    def tearDown(self):self.tmp.cleanup()
    def test_server_weight_limit_with_490_safety_ceiling(self):
        self.assertEqual(self.b.reserve('GET','https://api-contract.weex.com/capi/v3/market/klines'),1)
        with self.b.db() as c:c.execute('INSERT INTO api_calls_v1 VALUES(?,?,?,?)',(self.clock(),489,0,'test'))
        with self.assertRaisesRegex(BudgetDeferred,'WAIT_API_REQUEST_WEIGHT_BUDGET'):
            self.b.reserve('GET','https://api-contract.weex.com/capi/v3/market/klines')
    def test_header_discovers_shorter_window(self):
        self.b.observe(200,{'X-USED-WEIGHT-10S':'34','X-REMAINING-WEIGHT-10S':'466'})
        limits=self.b.used()['limits']
        self.assertTrue(any(x['type']=='REQUEST_WEIGHT' and x['windowSeconds']==10 and x['limit']==490 for x in limits))
    def test_orders_use_their_own_server_bucket(self):
        with self.b.db() as c:c.execute('INSERT INTO api_calls_v1 VALUES(?,?,?,?)',(self.clock(),0,300,'test'))
        with self.assertRaisesRegex(BudgetDeferred,'WAIT_API_ORDERS_BUDGET'):
            self.b.reserve('POST','https://api-contract.weex.com/capi/v3/order')
    def test_429_pause_is_exchange_backoff_not_local_ten_minutes(self):
        self.b.observe(429,{'Retry-After':'2'})
        self.assertEqual(self.b.used()['pauseUntil'],self.clock()+10)
    def test_429_honors_http_date_retry_after(self):
        self.b.observe(429,{'Retry-After':formatdate(self.clock()+23,usegmt=True)})
        self.assertEqual(self.b.used()['pauseUntil'],self.clock()+23)

if __name__=='__main__':unittest.main()
