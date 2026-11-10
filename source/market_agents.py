"""Deterministic WEEX market agents, diagnostics only; no orders."""
from __future__ import annotations
import json,time
from datetime import datetime,timezone
from pathlib import Path
from weex_ai_signals import candles,ema
ROOT=Path(__file__).resolve().parent
SIGNAL_PROFILE='TREND_5M_15M_VOLUME_90_V1'
MIN_VOLUME_RATIO=0.9
REQUIRED_TREND_TIMEFRAMES=('5m','15m')

def trend_matches(trend,side):
 """1h remains observed but does not veto the two execution timeframes."""
 directions=trend.get('timeframes')
 return (side in ('LONG','SHORT') and trend.get('aligned') is True
         and isinstance(directions,list) and len(directions)==3
         and directions[:2]==[side]*2 and directions[2] in ('LONG','SHORT'))
def analyze(symbol,*,candle_reader=None):
 reports={};closed_times={}
 for tf in ("5m","15m","1h"):
  rows=(candle_reader or candles)(symbol,tf,85)
  closed_times[tf]=int(rows[-1][6])
  close=[float(x[4]) for x in rows]
  high=[float(x[2]) for x in rows]
  low=[float(x[3]) for x in rows]
  vol=[float(x[5]) for x in rows]
  f=ema(close,12);slow=ema(close,26)
  tr=[max(high[i]-low[i],abs(high[i]-close[i-1]),abs(low[i]-close[i-1])) for i in range(1,len(rows))]
  atr=sum(tr[-14:])/14
  avgvol=sum(vol[-21:-1])/20
  reports[tf]={"price":close[-1],"direction":"LONG" if f>slow else "SHORT",
               "atrPct":atr/close[-1]*100,"volumeRatio":vol[-1]/avgvol if avgvol>0 else 0,
               "spreadProxy":(high[-1]-low[-1])/close[-1]*100}
 trends=[reports[x]["direction"] for x in ("5m","15m","1h")]
 agreed=trends[0]==trends[1]
 liquidity_ok=reports["5m"]["spreadProxy"]<2 and reports["5m"]["volumeRatio"]>.5
 momentum_ok=reports["5m"]["volumeRatio"]>=MIN_VOLUME_RATIO
 result=trends[0] if agreed and liquidity_ok and momentum_ok else "WAIT"
 return {"symbol":symbol,"decision":result,"strategyProfile":SIGNAL_PROFILE,
         "trend":{"aligned":agreed,"timeframes":trends,"requiredTimeframes":list(REQUIRED_TREND_TIMEFRAMES),"allTimeframesAligned":len(set(trends))==1},
         "momentum":{"volumeRatio":round(reports["5m"]["volumeRatio"],3),"confirmed":momentum_ok},
         "liquidity":{"proxyOnly":True,"passed":liquidity_ok,"note":"Candle range is not order-book spread"},
         "reasons":["5m/15m trend alignment: "+str(agreed),"Momentum volume >= 0.9: "+str(momentum_ok),
                    "Candle volatility proxy check: "+str(liquidity_ok)],
         "timeframes":reports,"closedCandleTimes":closed_times,
         "observedAt":datetime.now(timezone.utc).isoformat(),"orderPermitted":False}
def run(max_pairs=12):
 uni=json.loads((ROOT/"universe_latest.json").read_text(encoding="utf-8"))
 results=[]
 for s in uni["symbols"][:max_pairs]:
  try:results.append(analyze(s["symbol"]))
  except Exception as exc:results.append({"symbol":s["symbol"],"decision":"ERROR","error":type(exc).__name__})
 payload={"asOf":datetime.now(timezone.utc).isoformat(),"agentName":"WEEX deterministic research agents",
          "status":"DIAGNOSTIC_ONLY","liveTrading":False,"results":results}
 p=ROOT/"market_agents_latest.json"
 tmp=p.with_suffix(".tmp");tmp.write_text(json.dumps(payload,indent=2),encoding="utf-8");tmp.replace(p)
 return payload
if __name__=="__main__":
 x=run();print("analyzed",len(x["results"]),"decisions",[(r["symbol"],r["decision"]) for r in x["results"]])
