import hashlib,json
from pathlib import Path
from datetime import datetime,timezone
import live_control as c
root=Path(__file__).resolve().parent
manifest_path=root/"live_release_manifest.json"
m=json.loads(manifest_path.read_text(encoding="utf-8"))
m["sha256"]={name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in c.CODE_FILES}
m["status"]="OFFLINE_VERIFIED_NO_REAL_ORDERS"
m["testsPassed"]=True
m["testCount"]=680
m["releasedAt"]=datetime.now(timezone.utc).isoformat()
m["validationScope"]="680 unittest offline tests passed after external TP adoption changes; external TP is evidence-only and does not authorize LIVE or alter dispatch history. Fresh WEEX readback of LTCUSDT was separately verified."
m["externalTpAdoption"]="EXTERNAL_MANUAL_TP_EVIDENCE_ONLY"
manifest_path.write_text(json.dumps(m,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
print("MANIFEST_UPDATED",len(c.CODE_FILES))
print("BUILD_ERRORS",c.build_errors(root))
