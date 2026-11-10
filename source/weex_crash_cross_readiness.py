"""Consolidated non-authorizing WEEX readiness evidence (read-only).

The OS crash drill is local-only and MUST NEVER satisfy the independent
exchange-live crash/restart gate. The cross audit is a risk assessment,
not a cross-margin safety certificate.
"""
from datetime import datetime,timezone
from pathlib import Path
import json,os
from weex_os_crash_journal_drill import run as crash
from weex_full_lifecycle_os_crash_drill import run as full_lifecycle_crash
from weex_cross_margin_risk_audit import audit as cross
from weex_live_new_entry_guard import evaluate as entry_guard
from live_control import state,build_errors,configuration

def run(root=None):
 root=Path(root or Path(__file__).resolve().parent)
 if state(root)['mode']!='STOPPED':raise PermissionError('LIVE_NOT_STOPPED')
 cfg,_=configuration(root)
 gate=json.loads((root/'live_release_gate_latest.json').read_text(encoding='utf-8'))
 rec=json.loads((root/'account_reconciliation_point1_latest.json').read_text(encoding='utf-8'))
 cross_report=cross(root)
 crash_report=crash()
 full_crash_report=full_lifecycle_crash()
 check=entry_guard(cfg,[],[],[])
 blockers=list(check['issues'])
 if gate.get('gate')!='GO':blockers.append('INDEPENDENT_RELEASE_GATE_NO_GO')
 if not crash_report['liveExchangeCrashCertified']:blockers.append('WEEX_REAL_ORDER_CRASH_NOT_VERIFIED')
 if not cross_report['lossCeilingCertified']:blockers.append('CROSS_ACCOUNT_LOSS_CEILING_UNVERIFIED')
 if build_errors(root):blockers.append('OFFLINE_RELEASE_MANIFEST_INVALID')
 out={'checkedAt':datetime.now(timezone.utc).isoformat(),'state':'NO_GO',
 'orderDispatchAuthorized':False,'liveSwitch':state(root)['mode'],
 'offlineReleaseIntegrityOK':not build_errors(root),
 'independentReleaseGate':gate.get('gate'),
 'independentReleaseChecksPassed':gate.get('passed'),
 'independentReleaseChecksTotal':gate.get('total'),
 'operationalReconciliation':rec.get('status'),
 'crossMarginRisk':cross_report,'osProcessCrash':crash_report,
 'fullLifecycleCrashWithSimulatedExchange':full_crash_report,
 'tpBeforeSendInterruptionBlocksFurtherEntry':any(
    x['crashPoint']=='TP_BEFORE_SEND' and x['postRestartState']=='TP_PENDING' and
    x['afterTpWrites']==0 for x in full_crash_report['results']),
 'remainingBlockers':sorted(set(blockers)),
 'exchangeWrites':0,'telegramMessages':0}
 path=root/'weex_crash_cross_readiness_latest.json'
 tmp=path.with_suffix('.tmp')
 tmp.write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
 os.replace(tmp,path)
 return {'state':out['state'],'liveSwitch':out['liveSwitch'],
         'releaseGate':out['independentReleaseGate'],
         'blockers':out['remainingBlockers'],'crashScenarios':len(crash_report['checks']),
         'exchangeWrites':0}
if __name__=='__main__':print(json.dumps(run(),indent=2))
