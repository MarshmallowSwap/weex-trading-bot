import json,sys,urllib.request
sys.path.insert(0,r"D:\FUNDSHOT\weex_alerts")
from monitor import TG
from telegram_ai_settings import message,keyboard
cfg=json.loads(TG.read_text(encoding="utf-8"))
token=cfg["telegram_bot_token"]
def api(method,args):
 req=urllib.request.Request("https://api.telegram.org/bot"+token+"/"+method,data=json.dumps(args).encode(),headers={"Content-Type":"application/json"})
 with urllib.request.urlopen(req,timeout=20) as r:return json.load(r)
w=api("getWebhookInfo",{})
print("webhook_active",bool(w.get("result",{}).get("url")))
r=api("sendMessage",{"chat_id":cfg["telegram_chat_id"],"text":message(),"reply_markup":keyboard()})
print("menu_delivered",r.get("ok"),"message_id",r.get("result",{}).get("message_id"))
