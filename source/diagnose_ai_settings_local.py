import json,sys,sqlite3
from pathlib import Path
sys.path.insert(0,r"D:\FUNDSHOT\weex_alerts")
from monitor import TG,ROOT
c=json.loads(TG.read_text(encoding="utf-8"))
chat=str(c.get("telegram_chat_id",""))
print("chat_kind", "group_or_channel" if chat.startswith("-") else "private")
print("has_user_id",bool(c.get("telegram_user_id")))
print("has_token",bool(c.get("telegram_bot_token")))
db=sqlite3.connect(str(ROOT/"telegram_commands.sqlite3"))
print("cursor",db.execute("select * from cursor").fetchall())
print("state",db.execute("select * from input_state").fetchall())
