import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from tp_sl_strategy_engine import evaluate
P={"side":"LONG","avg_entry_price":"100","base_quantity":"10","allocated_open_fee_usdt":"0.8","net_funding_paid_usdt":"0"}
M={"mark_price":"100","atr":"1","taker_fee_rate":"0.0008"}
BASE={"tpMode":"fixed","slMode":"off","targetNetProfitUSDT":1,"marginUSDT":5,"tpRoiPercent":20,"slLossPercent":25,"atrTakeMultiplier":2,"atrStopMultiplier":2,"minProfitUSDT":0.5,"fixedStopPrice":"98"}
class TestStrategies(unittest.TestCase):
 def test_modes(self):
  for tp in ("fixed","percent","dynamic","hybrid","trailing"):
   for sl in ("off","fixed","percent","atr","ai","trailing"):
    with self.subTest(tp=tp,sl=sl):
     s=dict(BASE,tpMode=tp,slMode=sl)
     r=evaluate(P,s,M)
     self.assertFalse(r["orderSubmissionEnabled"])
     if tp=="trailing":self.assertIsNone(r["tp"])
     if sl=="off":self.assertIsNone(r["sl"])
 def test_invalid(self):
  with self.assertRaises(ValueError):evaluate(P,dict(BASE,tpMode="invalid"),M)
 def test_no_order_api(self):
  import inspect,tp_sl_strategy_engine
  code=inspect.getsource(tp_sl_strategy_engine)
  self.assertNotIn("urllib.request",code)
if __name__=="__main__":unittest.main()
