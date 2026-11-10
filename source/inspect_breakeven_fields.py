"""Inspect WEEX position response KEYS only. No order submission, no account amounts."""
import json,time,base64,hmac,hashlib,urllib.request,pathlib
base=pathlib.Path(__file__).parent
cfg=json.loads((base/"weex_credentials.json").read_text(encoding="utf-8"))
path="/capi/v3/account/position/allPosition"
ts=str(int(time.time()*1000))
sig=base64.b64encode(hmac.new(cfg["secret_key"].encode(),(ts+"GET"+path).encode(),hashlib.sha256).digest()).decode()
headers={"ACCESS-KEY":cfg["api_key"],"ACCESS-SIGN":sig,"ACCESS-PASSPHRASE":cfg["passphrase"],"ACCESS-TIMESTAMP":ts,"Content-Type":"application/json"}
req=urllib.request.Request("https://api-contract.weex.com"+path,headers=headers)
try:
 with urllib.request.urlopen(req,timeout=16) as r: obj=json.load(r)
 if isinstance(obj,list):
  print("type=list; position_count=",len(obj))
  for p in obj[:4]:print("symbol=",p.get("symbol"),"fields=",sorted(p.keys()),"breakEvenKeys=",[k for k in p if "break" in k.lower() or "even" in k.lower()])
 elif isinstance(obj,dict):
  print("type=dict; fields=",sorted(obj.keys()),"message=",str(obj.get("msg",obj.get("message","")))[:120])
  for k,v in obj.items():
   if isinstance(v,list):
    print("list_field=",k,"length=",len(v))
    for p in v[:2]:
     if isinstance(p,dict):print("position_fields=",sorted(p.keys()))
 else:print("unexpected_type=",type(obj).__name__)
except Exception as e:
 print("failure_type=",type(e).__name__,"status=",getattr(e,"code","n/a"))
