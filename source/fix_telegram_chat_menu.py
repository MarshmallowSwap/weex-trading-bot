import json,sys,urllib.request
sys.path.insert(0,r"D:\FUNDSHOT\weex_alerts")
from monitor import TG
c=json.loads(TG.read_text(encoding="utf-8"));base="https://api.telegram.org/bot"+c["telegram_bot_token"]+"/"
def call(method,payload):
 req=urllib.request.Request(base+method,json.dumps(payload).encode(),headers={"Content-Type":"application/json"})
 with urllib.request.urlopen(req,timeout=15) as r:
  value=json.load(r)
  if not value.get("ok"):raise RuntimeError(method)
  return value["result"]
chat=int(c["telegram_chat_id"])
scope={"type":"chat","chat_id":chat}
existing=call("getMyCommands",{"scope":scope})
if not any(x.get("command")=="settings" for x in existing):
 existing.insert(0,{"command":"settings","description":"Impostazioni WEEX AI Desk e Take Profit"})
call("setMyCommands",{"scope":scope,"commands":existing})
readback=call("getMyCommands",{"scope":scope})
print("specific_chat_commands",[(i["command"]) for i in readback])
print("settings_verified",any(i["command"]=="settings" for i in readback))
