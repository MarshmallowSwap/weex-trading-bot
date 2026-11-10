from pathlib import Path
p=Path(r"D:\FUNDSHOT\weex_alerts\commands.py")
s=p.read_text(encoding="utf-8")
assert "from agents_status_card import render" not in s
s=s.replace("from agents_status import status as agent_status","from agents_status import status as agent_status\nfrom agents_status_card import render as render_agents_card")
needle='''def snapshot():'''
send='''def send_agents_photo(token,chat):
    image_path,states=render_agents_card()
    boundary="----WEEXAIStatusBoundary"
    caption="🤖 WEEX AI DESK — Stato reale\\nScanner: "+states["scanner"]+" | Strategy: "+states["strategy"]+"\\nLive: "+("CONFIGURATO ON" if states["live"] else "OFF")
    data=image_path.read_bytes()
    body=(("--"+boundary+"\\r\\nContent-Disposition: form-data; name=\\\"chat_id\\\"\\r\\n\\r\\n"+chat+"\\r\\n"
           "--"+boundary+"\\r\\nContent-Disposition: form-data; name=\\\"caption\\\"\\r\\n\\r\\n"+caption+"\\r\\n"
           "--"+boundary+"\\r\\nContent-Disposition: form-data; name=\\\"photo\\\"; filename=\\\"agents_status.png\\\"\\r\\n"
           "Content-Type: image/png\\r\\n\\r\\n").encode("utf-8")+data+("\\r\\n--"+boundary+"--\\r\\n").encode("utf-8"))
    request=urllib.request.Request("https://api.telegram.org/bot"+token+"/sendPhoto",body,headers={"Content-Type":"multipart/form-data; boundary="+boundary})
    with urllib.request.urlopen(request,timeout=30) as response:
        result=json.load(response)
    if not result.get("ok"):raise RuntimeError("Telegram sendPhoto error")
    return result["result"]

'''
assert needle in s
s=s.replace(needle,send+needle)
old='''                    elif command=="/agents" and from_id==allowed_user:
                        api(token,"sendMessage",{"chat_id":chat,"text":agent_status()})'''
new='''                    elif command=="/agents" and from_id==allowed_user:
                        try:
                            send_agents_photo(token,chat)
                        except Exception:
                            logging.exception("WEEX AI graphic failed")
                            api(token,"sendMessage",{"chat_id":chat,"text":agent_status()})'''
assert old in s
s=s.replace(old,new)
p.with_suffix(".py.bak_agents_graphics").write_text(p.read_text(encoding="utf-8"),encoding="utf-8")
p.write_text(s,encoding="utf-8")
