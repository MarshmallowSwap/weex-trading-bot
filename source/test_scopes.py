import json,time,base64,hmac,hashlib,urllib.request,urllib.error,pathlib
cfg=json.loads((pathlib.Path(__file__).parent/"weex_credentials.json").read_text(encoding="utf-8"))
routes=[("FUTURES_ACCOUNT","https://api-contract.weex.com","/capi/v3/account/accountConfig"),("FUTURES_BALANCE","https://api-contract.weex.com","/capi/v3/account/balance"),("SPOT_ACCOUNT","https://api-spot.weex.com","/api/v3/account/assets-overview")]
for title,base,path in routes:
 ts=str(int(time.time()*1000));msg=ts+"GET"+path
 sig=base64.b64encode(hmac.new(cfg["secret_key"].encode(),msg.encode(),hashlib.sha256).digest()).decode()
 req=urllib.request.Request(base+path,headers={"ACCESS-KEY":cfg["api_key"],"ACCESS-SIGN":sig,"ACCESS-PASSPHRASE":cfg["passphrase"],"ACCESS-TIMESTAMP":ts,"Content-Type":"application/json","locale":"en-US"})
 try:
  with urllib.request.urlopen(req,timeout=14) as r:
   obj=json.load(r)
  print(title,"HTTP_OK","TYPE",type(obj).__name__)
  if isinstance(obj,dict):print("CODE",obj.get("code"),"MSG",str(obj.get("msg",""))[:90])
  elif isinstance(obj,list):print("RECORDS",len(obj))
 except urllib.error.HTTPError as e:
  try:
   body=json.loads(e.read(1024).decode())
   print(title,"HTTP",e.code,"API_CODE",body.get("code"),"API_MSG",str(body.get("msg",body.get("message","")))[:100])
  except Exception:print(title,"HTTP",e.code,"BODY_UNREADABLE")
 except Exception as e:print(title,type(e).__name__,str(e)[:95])
