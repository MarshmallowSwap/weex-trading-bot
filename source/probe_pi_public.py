"""Read-only endpoint check for PIUSDT errors; no credentials or order actions."""
import urllib.request,urllib.error
base="https://api-contract.weex.com"
for path in ("/capi/v3/market/klines?symbol=PIUSDT&interval=5m&limit=85","/capi/v3/market/depth?symbol=PIUSDT&limit=15"):
 try:
  with urllib.request.urlopen(urllib.request.Request(base+path,headers={"User-Agent":"WEEX-AI-AUDIT/1"}),timeout=12) as r:print(path.split("?")[0],r.status)
 except urllib.error.HTTPError as e:print(path.split("?")[0],"HTTP",e.code)
 except Exception as e:print(path.split("?")[0],type(e).__name__)
