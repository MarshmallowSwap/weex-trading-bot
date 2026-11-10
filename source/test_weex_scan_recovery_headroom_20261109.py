"""Offline tests: public scanner must not starve authenticated recovery API."""
import tempfile,unittest,threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch
from weex_scan_data import PublicData,ScanBudgetExceeded,MAX_PUBLIC_SCANNER_REQUESTS_PER_CYCLE

class ScannerHeadroom(unittest.TestCase):
 def test_bound_exactly_at_limit(self):
  with tempfile.TemporaryDirectory() as td:
   p=PublicData(Path(td),clock=lambda:1000,deadline_seconds=180)
   for _ in range(MAX_PUBLIC_SCANNER_REQUESTS_PER_CYCLE):p.reserve()
   self.assertEqual(p.requests,MAX_PUBLIC_SCANNER_REQUESTS_PER_CYCLE)
   with self.assertRaisesRegex(ScanBudgetExceeded,'RECOVERY_API_HEADROOM'):p.reserve()
   self.assertEqual(p.requests,MAX_PUBLIC_SCANNER_REQUESTS_PER_CYCLE)
 def test_concurrent_reservation_does_not_exceed_budget(self):
  with tempfile.TemporaryDirectory() as td:
   p=PublicData(Path(td),clock=lambda:1000,deadline_seconds=180)
   def invoke(_):
    try:p.reserve();return True
    except ScanBudgetExceeded:return False
   with ThreadPoolExecutor(max_workers=16) as pool:
    accepted=list(pool.map(invoke,range(320)))
   self.assertEqual(sum(accepted),MAX_PUBLIC_SCANNER_REQUESTS_PER_CYCLE)
 def test_shared_budget_stops_scanner_before_account_starvation(self):
  with tempfile.TemporaryDirectory() as td:
   p=PublicData(Path(td),clock=lambda:1000,deadline_seconds=180)
   with patch('weex_api_budget.Budget.used',return_value={'weight':300}):
    with self.assertRaisesRegex(ScanBudgetExceeded,'SHARED_RECOVERY_API_HEADROOM'):
     p.reserve()
   self.assertEqual(p.requests,0)
 def test_deadline_always_fails_closed(self):
  with tempfile.TemporaryDirectory() as td:
   p=PublicData(Path(td),clock=lambda:1000,deadline_seconds=0)
   with self.assertRaisesRegex(ScanBudgetExceeded,'SCAN_DEADLINE'):p.reserve()
 def test_no_network_on_quota_exhaustion(self):
  with tempfile.TemporaryDirectory() as td:
   call=[]
   def opener(*args,**kwargs):call.append(True);raise AssertionError('NETWORK_FORBIDDEN')
   p=PublicData(Path(td),clock=lambda:1000,deadline_seconds=180,opener=opener)
   p.requests=MAX_PUBLIC_SCANNER_REQUESTS_PER_CYCLE
   with self.assertRaises(ScanBudgetExceeded):
    p.open('https://api-contract.weex.com/capi/v3/market/klines?symbol=ETHUSDT')
   self.assertFalse(call)

if __name__=='__main__':unittest.main()
