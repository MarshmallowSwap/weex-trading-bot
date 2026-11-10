from pathlib import Path
import json,datetime,hashlib
r=Path(__file__).resolve().parent
files=['weex_live_new_entry_guard.py','live_release_gate.py','weex_final_release_decision.py',
 'weex_worker_recovery_readonly_20261109.py','weex_supervised_process_monitor_v6.py',
 'weex_supervisor_promotion_policy_v16.py','weex_ai_risk_config.json',
 'weex_live_worker.py','weex_multi_symbol_ownership_v12.py',
 'weex_manual_position_ack.py']
for name in files:
 p=r/name
 if p.exists():
  print('MODULE',name,'modified',datetime.datetime.fromtimestamp(p.stat().st_mtime).isoformat(timespec='seconds'),
        'sha256',hashlib.sha256(p.read_bytes()).hexdigest()[:14])
for name in ('live_release_gate_latest.json','weex_final_release_decision_latest.json','WEEX_LIVE_DECISION_REPORT.json'):
 p=r/name
 if p.exists():
  try:
   d=json.loads(p.read_text(encoding='utf-8'))
   print('GATE',name,{k:d.get(k) for k in ('checkedAt','status','passed','total','blockers','remaining','decision','go','mode','reasons','reason') if k in d})
  except Exception as e:print('GATE_ERR',name,type(e).__name__)
