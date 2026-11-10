from pathlib import Path
p=Path(r"D:\FUNDSHOT\weex_alerts\position_manager_integrated.py")
s=p.read_text(encoding="utf-8")
s=s.replace("from protection_policy import classify","from protection_policy import classify\nfrom position_ownership_gate import authorize")
s=s.replace('"policy":policy,"quantitiesCertified":False,"modificationAllowed":False','"policy":policy,"ownership":authorize("CLOSE",p,[],reconciled=False),"quantitiesCertified":False,"modificationAllowed":False')
p.write_text(s,encoding="utf-8")
print("Ownership gate integrated into read-only position report")
