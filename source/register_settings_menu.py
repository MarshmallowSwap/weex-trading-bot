"""Update Telegram command menu for the existing WEEX bot without exposing secrets."""
import json, urllib.request, sys
sys.path.insert(0, r"D:\FUNDSHOT\weex_alerts")
from monitor import TG
cfg=json.loads(TG.read_text(encoding="utf-8"))
root="https://api.telegram.org/bot"+cfg["telegram_bot_token"]+"/"
def request(method,payload):
    req=urllib.request.Request(root+method,json.dumps(payload).encode(),headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req,timeout=20) as response:
        d=json.load(response)
    if not d.get("ok"): raise RuntimeError("Telegram returned error for "+method)
    return d["result"]
existing=request("getMyCommands",{})
commands={row["command"]:row["description"] for row in existing if isinstance(row,dict) and "command" in row}
commands["settings"]="Impostazioni AI Desk, margine e Take Profit"
for name,description in (("pnl","PnL realizzato WEEX"),("winrate","Win rate delle chiusure"),("help","Elenco comandi disponibili")):
    commands.setdefault(name,description)
payload=[{"command":key,"description":str(value)[:256]} for key,value in commands.items()]
request("setMyCommands",{"commands":payload})
actual=request("getMyCommands",{})
print("configured_count",len(actual))
print("settings_present",any(x.get("command")=="settings" for x in actual))
print("commands",",".join(x.get("command","") for x in actual))
