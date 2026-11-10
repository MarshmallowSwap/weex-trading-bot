from pathlib import Path
p=Path(r"D:\FUNDSHOT\weex_alerts\live_1x_close_plan.py")
s=p.read_text(encoding="utf-8").replace('pid=position.get("positionId")','pid=position.get("id")')
p.write_text(s,encoding="utf-8")
t=Path(r"D:\FUNDSHOT\weex_alerts\test_live_1x_close_plan.py")
v=t.read_text(encoding="utf-8").replace('"positionId":"123456"','"id":"123456"')
t.write_text(v,encoding="utf-8")
print("V3 id mapping updated")
