from pathlib import Path
p=Path(r"D:\FUNDSHOT\weex_alerts\test_live_sdk_end_to_end_audit.py")
s=p.read_text(encoding="utf-8").replace('"READ_ONLY_VERIFIED"','"READ_ONLY_MATCHED"')
p.write_text(s,encoding="utf-8")
print("Test expectation aligned to non-certifying READ_ONLY_MATCHED status")
