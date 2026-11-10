from pathlib import Path
p=Path(r"D:\FUNDSHOT\weex_alerts\commands.py")
s=p.read_text(encoding="utf-8")
s=s.replace('    caption="🤖 WEEX AI DESK — Stato reale\\nScanner: "+states["scanner"]+" | Strategy: "+states["strategy"]+"\\nLive: "+("CONFIGURATO ON" if states["live"] else "OFF")\\n','')
start=s.index('    body=((',s.index('def send_agents_photo('))
end=s.index('    request=urllib.request.Request',start)
s=s[:start]+'''    body=(("--"+boundary+"\\r\\nContent-Disposition: form-data; name=\\\"chat_id\\\"\\r\\n\\r\\n"+chat+"\\r\\n"
           "--"+boundary+"\\r\\nContent-Disposition: form-data; name=\\\"photo\\\"; filename=\\\"agents_status.png\\\"\\r\\n"
           "Content-Type: image/png\\r\\n\\r\\n").encode("utf-8")+data+("\\r\\n--"+boundary+"--\\r\\n").encode("utf-8"))
'''+s[end:]
p.with_suffix(".py.bak_before_caption_remove").write_text(p.read_text(encoding="utf-8"),encoding="utf-8")
p.write_text(s,encoding="utf-8")
