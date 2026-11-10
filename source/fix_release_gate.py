from pathlib import Path
p=Path(r"D:\FUNDSHOT\weex_alerts\live_release_gate.py")
s=p.read_text(encoding="utf-8")
s=s.replace('  "execution_enabled":cfg.get("execution",{}).get("enabled") is True','  "execution_disabled_during_preflight":cfg.get("execution",{}).get("enabled") is False')
s=s.replace(' "gate":gate,"checks":checks,',' "gate":gate,"checks":checks,')
p.write_text(s,encoding="utf-8")
print("Preflight requires execution OFF until certification")
