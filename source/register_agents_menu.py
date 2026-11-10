import json,sys,urllib.request
sys.path.insert(0,r"D:\FUNDSHOT\weex_alerts")
from monitor import TG
cfg=json.loads(TG.read_text(encoding="utf-8"))
root="https://api.telegram.org/bot"+cfg["telegram_bot_token"]+"/"
def call(method,data):
 req=urllib.request.Request(root+method,json.dumps(data).encode(),headers={"Content-Type":"application/json"})
 with urllib.request.urlopen(req,timeout=15) as r:return json.load(r)["result"]
scope={"type":"chat","chat_id":int(cfg["telegram_chat_id"])}
current=call("getMyCommands",{"scope":scope})
if not any(c["command"]=="agents" for c in current):
 current.append({"command":"agents","description":"Stato reale degli agenti AI"})
call("setMyCommands",{"scope":scope,"commands":current})
print("menu_verified",[x["command"] for x in call("getMyCommands",{"scope":scope})])
