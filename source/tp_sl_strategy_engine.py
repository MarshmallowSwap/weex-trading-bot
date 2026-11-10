"""WEEX TP/SL strategy calculations. No exchange orders. All prices theoretical."""
from decimal import Decimal
from break_even_resolver import resolve,target_price
D=lambda v:Decimal(str(v))
TP=("fixed","dynamic","percent","trailing","hybrid")
SL=("off","fixed","percent","atr","trailing","ai")
def evaluate(position,settings,market):
 side=str(position["side"]).upper()
 if side not in ("LONG","SHORT"):raise ValueError("side")
 direction=D(1) if side=="LONG" else D(-1)
 entry=D(position["avg_entry_price"]);qty=D(position["base_quantity"])
 current=D(market["mark_price"]);atr=D(market["atr"])
 rate=D(market["taker_fee_rate"]);slippage=D(market.get("slippage_rate",0))
 if min(entry,qty,current,atr)<=0:raise ValueError("positive inputs required")
 be=resolve(position,closing_taker_rate=rate,expected_slippage_rate=slippage)
 tp_mode=settings["tpMode"];sl_mode=settings["slMode"]
 if tp_mode not in TP or sl_mode not in SL:raise ValueError("mode")
 if tp_mode=="fixed":
  tp=target_price(position,be,D(settings["targetNetProfitUSDT"]),closing_taker_rate=rate,expected_slippage_rate=slippage)
 elif tp_mode=="percent":
  desired=D(settings["marginUSDT"])*D(settings["tpRoiPercent"])/100
  tp=target_price(position,be,desired,closing_taker_rate=rate,expected_slippage_rate=slippage)
 elif tp_mode in ("dynamic","hybrid"):
  proposed=be.price+direction*atr*D(settings["atrTakeMultiplier"])
  floor=target_price(position,be,D(settings["minProfitUSDT"]),closing_taker_rate=rate,expected_slippage_rate=slippage)
  tp=max(proposed,floor) if side=="LONG" else min(proposed,floor)
 elif tp_mode=="trailing":
  tp=None
 else:raise ValueError("TP")
 stop=None
 if sl_mode=="fixed":stop=D(settings["fixedStopPrice"])
 if sl_mode=="percent":
  stop=entry-direction*(D(settings["marginUSDT"])*D(settings["slLossPercent"])/100/qty)
 if sl_mode=="atr":stop=current-direction*atr*D(settings["atrStopMultiplier"])
 if sl_mode=="ai":
  stop=current-direction*atr*D(settings["atrStopMultiplier"])
 # trailing only produces a candidate after favorable excursion; stateful high-water mark handled by position manager
 if sl_mode=="trailing":
  extremum=market.get("favorable_extreme")
  if extremum is not None:
   stop=D(extremum)-direction*atr*D(settings["atrStopMultiplier"])
 if stop is not None:
  if stop<=0 or (stop>=current if side=="LONG" else stop<=current):
   raise ValueError("Stop not on loss side of current mark")
 if tp is not None and (tp<=current if side=="LONG" else tp>=current):
  raise ValueError("TP must be on profit side of current mark")
 return {"breakEven":str(be.price),"tp":str(tp) if tp is not None else None,
         "sl":str(stop) if stop is not None else None,
         "tpMode":tp_mode,"slMode":sl_mode,"orderSubmissionEnabled":False,
         "warning":"Estimate; requires exchange tick/position checks and verified exit placement before trading."}
