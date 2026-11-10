from pathlib import Path
p=Path(r"D:\FUNDSHOT\weex_alerts\margin_mode_mismatch.py")
s=p.read_text(encoding="utf-8")
s=s.replace('mismatch=s["marginType"]!=target','mismatch=(str(s["marginType"]).upper() not in ({"CROSS","CROSSED"} if target in ("CROSS","CROSSED") else {target}))')
p.write_text(s,encoding="utf-8")
print("normalized Cross aliases")
