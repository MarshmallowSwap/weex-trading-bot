"""Bounded read-only refresh of live-release inputs for Telegram COLLAUDO.
No exchange writes, no start/stop switch, no live-worker invocation.
If a phase fails the gate is not auto-approved.
"""
import json,subprocess,sys,time
from pathlib import Path
from datetime import datetime,timezone
import live_control

ROOT=Path(__file__).resolve().parent
STEPS=(
 ('ACCOUNT_FRESH_GET',None,15),
 ('TP_COVERAGE_READONLY','position_manager_integrated.py',15),
 ('PAGED_TRADE_HISTORY_GET','live_pilot_paginated_reconciliation.py',25),
 ('FILL_IDENTITY_GET','reconcile_recent_fills_readonly.py',18),
 ('CURRENT_RECONCILIATION','account_reconciliation_point1.py',12),
 ('INDEPENDENT_RELEASE_GATE','live_release_gate.py',15),
)

def execute(root=ROOT):
    root=Path(root)
    report={'checkedAt':datetime.now(timezone.utc).isoformat(),'status':'INCOMPLETE',
       'mode':'READ_ONLY_REFRESH','exchangeWrites':0,'steps':[]}
    if live_control.state(root)['mode']!='STOPPED' or live_control.build_errors(root):
        report['status']='BLOCKED_NOT_STOPPED_OR_MANIFEST'
        return report
    cfg=json.loads((root/'weex_ai_risk_config.json').read_text(encoding='utf-8'))
    execution=cfg.get('execution',{})
    if execution.get('enabled') is not False or execution.get('mode')!='PRETRADE':
        report['status']='BLOCKED_CONFIG';return report
    for name,script,timeout in STEPS:
        command=([sys.executable,'-B','-c',
            "from weex_live_worker import Reader; from pathlib import Path; import sys; Reader(Path(sys.argv[1])).account(); print('GET_ONLY_OK')",str(root)]
            if script is None else [sys.executable,'-B',str(root/script)])
        if script and not (root/script).is_file():
            report['steps'].append({'name':name,'status':'MISSING'});break
        try:
            completed=subprocess.run(command,cwd=root,capture_output=True,text=True,timeout=timeout)
            ok=completed.returncode==0
            report['steps'].append({'name':name,'status':'PASS' if ok else 'FAILED',
               'exitCode':completed.returncode})
            if not ok:break
        except (OSError,subprocess.TimeoutExpired) as exc:
            report['steps'].append({'name':name,'status':type(exc).__name__});break
    report['status']='REFRESHED_READ_ONLY' if len(report['steps'])==len(STEPS) and all(
       x['status']=='PASS' for x in report['steps']) else 'INCOMPLETE'
    report['productionAuthorized']=False
    return report

if __name__=='__main__':
    print(json.dumps(execute(),ensure_ascii=False))
