"""WEEX demo-only signed transport, default dry-run. Production URL is impossible here."""
import base64,hashlib,hmac,json,time,urllib.request
from pathlib import Path
from weex_demo_firewall import authorize,BASE
ROOT=Path(__file__).resolve().parent
class DemoTransport:
 def __init__(self,credentials_path=None,write_enabled=False,opener=None):
  self.path=Path(credentials_path or ROOT/"weex_credentials.json")
  self.write_enabled=write_enabled
  self.opener=opener or urllib.request.urlopen
 def post_order(self,payload):
  if not isinstance(payload,dict):raise ValueError("Invalid payload")
  keys={"symbol","side","positionSide","type","quantity","newClientOrderId"}
  if not keys.issubset(payload):raise ValueError("Missing required fields")
  if payload["type"]=="LIMIT" and not {"price","timeInForce"}.issubset(payload):raise ValueError("Limit order parameters missing")
  if payload["side"] not in ("BUY","SELL") or payload["positionSide"] not in ("LONG","SHORT") or payload["type"] not in ("LIMIT","MARKET"):raise ValueError("Invalid order type")
  path="/capi/v3/sim/order"
  status=authorize("POST",BASE+path,payload["symbol"],allow_demo_writes=self.write_enabled)
  if not status["allowed"]:return {"sent":False,"reason":status["reason"]}
  body=json.dumps(payload,separators=(",",":"),ensure_ascii=False).encode("utf-8")
  cfg=json.loads(self.path.read_text(encoding="utf-8"))
  ts=str(int(time.time()*1000))
  digest=base64.b64encode(hmac.new(cfg["secret_key"].encode(),(ts+"POST"+path+body.decode()).encode(),hashlib.sha256).digest()).decode()
  headers={"ACCESS-KEY":cfg["api_key"],"ACCESS-SIGN":digest,"ACCESS-PASSPHRASE":cfg["passphrase"],"ACCESS-TIMESTAMP":ts,"Content-Type":"application/json"}
  req=urllib.request.Request(BASE+path,data=body,headers=headers,method="POST")
  with self.opener(req,timeout=20) as response:result=json.load(response)
  return {"sent":True,"accepted":result.get("success") is True,"orderId":str(result.get("orderId") or ""),"clientOrderId":result.get("clientOrderId"),"errorCode":result.get("errorCode")}
