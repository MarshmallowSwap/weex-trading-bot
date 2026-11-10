import json,sys,urllib.request
sys.path.insert(0,r"D:\FUNDSHOT\weex_alerts")
from monitor import TG
c=json.loads(TG.read_text(encoding="utf-8"));base="https://api.telegram.org/bot"+c["telegram_bot_token"]+"/"
def call(method,payload):
 req=urllib.request.Request(base+method,json.dumps(payload).encode(),headers={"Content-Type":"application/json"})
 with urllib.request.urlopen(req,timeout=15) as r:return json.load(r)["result"]
chat=int(c["telegram_chat_id"])
for label,payload in [("default",{}),("all_private",{"scope":{"type":"all_private_chats"}}),("specific_chat",{"scope":{"type":"chat","chat_id":chat}}),("default_it",{"language_code":"it"}),("chat_it",{"scope":{"type":"chat","chat_id":chat},"language_code":"it"})]:
 try:
  a=call("getMyCommands",payload)
  print(label,[(x["command"]) for x in a])
 except Exception as ex:print(label,type(ex).__name__)
print("menu_button",str(call("getChatMenuButton",{"chat_id":chat}))[:200])
