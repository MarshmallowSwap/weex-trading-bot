from weex_api_budget import open_url
"""Read live WEEX candles and propose explainable signals. Never places orders."""
import json, math, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parent
BASE="https://api-contract.weex.com/capi/v3/market/klines?"
def candles(symbol, interval, limit=85):
    query=urllib.parse.urlencode({"symbol":symbol,"interval":interval,"limit":limit})
    request=urllib.request.Request(BASE+query,headers={"User-Agent":"WEEX-AI-Desk/0.1"})
    with open_url(request,timeout=14) as response: rows=json.load(response)
    rows=sorted(rows,key=lambda x:int(x[0]))
    rows=[r for r in rows if int(r[6]) < int(datetime.now(timezone.utc).timestamp()*1000)]
    if len(rows)<35: raise ValueError("Insufficient completed candles")
    return rows
def ema(values,period):
    a=2/(period+1); out=values[0]
    for value in values[1:]:out=a*value+(1-a)*out
    return out
def analyze(symbol):
    readings={}
    for period in ("5m","15m","1h"):
        c=candles(symbol,period)
        close=[float(x[4]) for x in c]; highs=[float(x[2]) for x in c]; lows=[float(x[3]) for x in c]
        fast=ema(close,12); slow=ema(close,26)
        true_ranges=[max(highs[i]-lows[i],abs(highs[i]-close[i-1]),abs(lows[i]-close[i-1])) for i in range(1,len(c))]
        atr=sum(true_ranges[-14:])/14
        quote=[float(x[7]) for x in c]
        volume_ratio=quote[-1]/max(1e-9,sum(quote[-21:-1])/20)
        readings[period]={"price":close[-1],"trend":"LONG" if fast>slow else "SHORT",
                          "ema12":fast,"ema26":slow,"atrPct":100*atr/close[-1],
                          "volumeRatio":volume_ratio}
    trends=[readings[t]["trend"] for t in ("5m","15m","1h")]
    consistent=len(set(trends))==1
    side=trends[0] if consistent and readings["5m"]["volumeRatio"]>=1.05 else "WAIT"
    reasons=["all timeframes agree" if consistent else "timeframe disagreement",
             "5m relative volume "+str(round(readings["5m"]["volumeRatio"],2))]
    return {"symbol":symbol,"signal":side,"reasons":reasons,"timeframes":readings,
            "executionAllowed":False,"note":"Analytical diagnostics, not validated trade advice"}
if __name__=="__main__":
    src=json.loads((ROOT/"universe_latest.json").read_text(encoding="utf-8"))
    output={"asOf":datetime.now(timezone.utc).isoformat(),"liveMarketData":True,
            "realOrdersEnabled":False,"signals":[]}
    for entry in src["symbols"][:6]:
        try:output["signals"].append(analyze(entry["symbol"]))
        except Exception as ex:output["signals"].append({"symbol":entry["symbol"],"error":type(ex).__name__})
    (ROOT/"ai_signals_latest.json").write_text(json.dumps(output,indent=2),encoding="utf-8")
    for signal in output["signals"]:print(signal["symbol"],signal.get("signal",signal.get("error")))
