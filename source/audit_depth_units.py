"""Read-only dimensional audit: WEEX depth size vs contractVal metadata."""
import json,urllib.request,urllib.parse
from pathlib import Path
ROOT=Path(__file__).resolve().parent
info=json.load(urllib.request.urlopen("https://api-contract.weex.com/capi/v3/market/exchangeInfo?contractType=PERPETUAL",timeout=15))
lookup={s["symbol"]:s for s in info["symbols"]}
for symbol in ("BTCUSDT","ETHUSDT","SOLUSDT","1000PEPEUSDT","XPINUSDT"):
 try:
  req=urllib.request.Request("https://api-contract.weex.com/capi/v3/market/depth?"+urllib.parse.urlencode({"symbol":symbol,"limit":15}),headers={"User-Agent":"WEEX-AI-AUDIT/1"})
  d=json.load(urllib.request.urlopen(req,timeout=12))
  bid=d["bids"][0];a=d["asks"][0];s=lookup[symbol]
  print(symbol,"contractVal",s.get("contractVal"),"minOrderSize",s.get("minOrderSize"),"topBid",bid,"topAsk",a,"priceTimesSize",round(float(bid[0])*float(bid[1]),2),"priceTimesSizeTimesContractVal",round(float(bid[0])*float(bid[1])*float(s.get("contractVal") or 1),4))
 except Exception as error:print(symbol,type(error).__name__)
