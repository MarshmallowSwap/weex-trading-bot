import base64,hashlib,hmac,json,time,urllib.request,urllib.error
from pathlib import Path
from urllib.parse import urlencode
c=json.loads((Path(__file__).parent/"weex_credentials.json").read_text(encoding="utf-8"))
base="https://api-contract.weex.com"
paths=[
"/capi/v3/userTrades?limit=5",
"/capi/v3/order/history?limit=5&page=0",
"/capi/v3/allAlgoOrders?limit=5",
]
for path in paths:
 ts=str(int(time.time()*1000))
 raw=ts+"GET"+path
 sig=base64.b64encode(hmac.new(c["secret_key"].encode(),raw.encode(),hashlib.sha256).digest()).decode()
 req=urllib.request.Request(base+path,headers={"ACCESS-KEY":c["api_key"],"ACCESS-SIGN":sig,"ACCESS-PASSPHRASE":c["passphrase"],"ACCESS-TIMESTAMP":ts,"Content-Type":"application/json"})
 try:
  with urllib.request.urlopen(req,timeout=20) as res: result=json.load(res)
  print(path.split("?")[0],"OK","shape",type(result).__name__,
        "count",len(result) if isinstance(result,list) else "",
        "keys",list(result.keys())[:12] if isinstance(result,dict) else "",
        "sample_keys",list(result[0].keys())[:18] if isinstance(result,list) and result and isinstance(result[0],dict) else "")
 except urllib.error.HTTPError as e:
  try:
   b=json.loads(e.read(1500)); print(path.split("?")[0],"HTTP",e.code,"code",b.get("code"),"message",str(b.get("msg"))[:120])
  except Exception:print(path.split("?")[0],"HTTP",e.code)
 except Exception as e:print(path.split("?")[0],"ERROR",type(e).__name__,str(e)[:130])
