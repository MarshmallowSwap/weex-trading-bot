"""Immutable production integration readiness audit; never changes release gate or writes orders."""
import json,hashlib
from pathlib import Path
from datetime import datetime,timezone
import live_control
from weex_supervised_crash_executor_v2 import CLIENT_ID
from weex_real_worker_crash_evidence_gate import certify
ROOT=Path(__file__).resolve().parent
def run(root=ROOT):
 root=Path(root)
 from weex_live_worker import Reader
 from weex_api_budget import Budget
 cfg=json.loads((root/'weex_ai_risk_config.json').read_text(encoding='utf-8'))
 manifest=json.loads((root/'live_release_manifest.json').read_text(encoding='utf-8'))
 declared=manifest['sha256']
 hashes={p:hashlib.sha256((root/p).read_bytes()).hexdigest()==h for p,h in declared.items()}
 source=(root/'weex_lifecycle.py').read_text(encoding='utf-8')
 close=(root/'weex_pilot_emergency_close_sdk.py').read_text(encoding='utf-8')
 proof=certify(root)
 blockers=[]
 if cfg['risk']['minimumLeverage']!=100:blockers.append('STRATEGY_NOT_100X')
 if cfg['execution']['enabled'] is not False or live_control.state(root)['mode']!='STOPPED':
  blockers.append('AUTOMATIC_BOT_MUST_REMAIN_STOPPED_FOR_TEST')
 if not all(hashes.values()):blockers.append('PRODUCTION_CODE_HASH_MISMATCH')
 if not CLIENT_ID.startswith('wxentry_'):blockers.append('PILOT_ID_NOT_PRODUCTION_TRADE_ID')
 if ("p.get('entrySource')=='supervised_crash_pilot'" not in source
     or "p['entry']['slTriggerPrice']=str(stop)" not in source):
  blockers.append('PRODUCTION_LIFECYCLE_DROPS_ATOMIC_ATTACHED_STOP')
 close_v3=root/'weex_supervised_exact_close100_v3.py'
 if not close_v3.is_file():
  blockers.append('DEDICATED_CROSS100_POSITION_CLOSE_MISSING')
 else:
  code=close_v3.read_text(encoding='utf-8')
  if 'CLOSE_ALREADY_RESERVED_NO_RETRY' not in code or 'EXACT_POSITION_CHANGED' not in code:
   blockers.append('CROSS100_CLOSE_INTENT_OR_ID_NOT_GUARDED')
  # The adapter is built and unit-tested, not yet exercised against WEEX.
  blockers.append('CROSS100_CLOSE_NOT_REAL_EXCHANGE_VERIFIED')
 if 'if release_gate_errors(root):raise PermissionError' in (root/'live_control.py').read_text(encoding='utf-8'):
  blockers.append('REAL_ENTRY_REQUIRES_DISTINCT_CERTIFIED_ONE_SHOT_AUTHORIZATION')
 if proof.get('certified') is not True:
  blockers.append('REAL_WORKER_ACK_CRASH_NOT_CERTIFIED')
 return {'checkedAt':datetime.now(timezone.utc).isoformat(),
  'status':'BLOCKED_FOR_REAL_POST' if blockers else 'READY_FOR_EXTERNAL_REVIEW',
  'scope':'PRODUCTION_SAFETY_INTEGRATION','botMode':live_control.state(root)['mode'],
  'codeHashesAllMatch':all(hashes.values()),
  'localApiBudget':Budget(root).used(),'blockers':blockers,
  'exchangeWrites':0,'releaseGateChanged':False,
  'doesNotCertifyLiveTest':True}
if __name__=='__main__':
 print(json.dumps(run(),ensure_ascii=False))
