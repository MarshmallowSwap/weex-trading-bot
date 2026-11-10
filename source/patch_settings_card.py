from pathlib import Path
p=Path(r"D:\FUNDSHOT\weex_alerts\commands.py")
s=p.read_text(encoding="utf-8")
s=s.replace("from agents_status_card import render as render_agents_card","from agents_status_card import render as render_agents_card\nfrom settings_card import render as render_settings_card")
anchor="def snapshot():"
method='''def send_settings_card(token,chat):
    image_path=render_settings_card()
    boundary="----WEEXSettingsCardBoundary"
    keyboard_data=json.dumps(full_menu(),ensure_ascii=False)
    data=image_path.read_bytes()
    fields=[("chat_id",chat),("reply_markup",keyboard_data)]
    body=b""
    for key,value in fields:
        body+=("--"+boundary+"\\r\\nContent-Disposition: form-data; name=\\\""+key+"\\\"\\r\\n\\r\\n"+value+"\\r\\n").encode("utf-8")
    body+=("--"+boundary+"\\r\\nContent-Disposition: form-data; name=\\\"photo\\\"; filename=\\\"settings.png\\\"\\r\\nContent-Type: image/png\\r\\n\\r\\n").encode("utf-8")+data+("\\r\\n--"+boundary+"--\\r\\n").encode("utf-8")
    request=urllib.request.Request("https://api.telegram.org/bot"+token+"/sendPhoto",body,headers={"Content-Type":"multipart/form-data; boundary="+boundary})
    with urllib.request.urlopen(request,timeout=30) as resp:result=json.load(resp)
    if not result.get("ok"):raise RuntimeError("settings sendPhoto failed")
    return result["result"]

'''
assert anchor in s
s=s.replace(anchor,method+anchor)
old='api(token,"sendMessage",{"chat_id":chat,"text":full_summary(),"reply_markup":full_menu()})'
assert s.count(old)>=2
s=s.replace(old,'send_settings_card(token,chat)')
p.with_suffix(".py.bak_settings_card").write_text(p.read_text(encoding="utf-8"),encoding="utf-8")
p.write_text(s,encoding="utf-8")
