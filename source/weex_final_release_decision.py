"""One decision report: never changes trading mode or submits exchange orders."""
import json,os
from pathlib import Path
from datetime import datetime,timezone
from decimal import Decimal
import live_control
R=Path(__file__).resolve().parent
def load(n):return json.loads((R/n).read_text(encoding='utf-8'))
cfg=load('weex_ai_risk_config.json')
gate=load('live_release_gate_latest.json')
econ=load('weex_economic_fills_readonly_latest.json')
pilot=load('weex_existing_account_1x_pilot_latest.json')
recovery=load('crash_recovery_readonly_latest.json')
worker=load('weex_live_worker_latest.json')
state=live_control.state(R)
report={'checkedAt':datetime.now(timezone.utc).isoformat(),
        'decision':'NO_GO' if gate['gate']!='GO' or live_control.readiness(R) else 'READY_FOR_USER_CONFIRMATION',
        'liveStarted':state['mode']=='RUNNING','mode':state['mode'],
        'entryCostUSDT':cfg['risk']['orderCostTargetUSDT'],
        'tpGrossUSDT':cfg['strategySettings']['targetNetProfitUSDT'],
        'marginMode':cfg['risk']['marginModePreference'],
        'integrityErrors':live_control.build_errors(R),
        'workerStatus':worker.get('status'),'accountReadOK':worker.get('accountReadOK'),
        'recoveryClear':worker.get('recoveryClear'),
        'releaseGate':gate['gate'],'releaseFailures':[k for k,v in gate['checks'].items() if v is not True],
        'economicOrdersVerified':econ['ordersWithEconomicEvidence'],
        'economicOrdersSampled':econ['distinctOrderIds'],
        'economicExceptions':econ['unverifiedOrders'],
        'crashLiveCertified':recovery['recoveryCertified'],
        'pilotEntryAuthorized':pilot['pilotExecutionAllowed'],
        'pilotBlockers':pilot['blockers'],
        'ordersSentByThisReport':0,
        'requiredForRealPilot':['Verified non-destructive emergency close route',
                                 'Pilot-specific authorization path independent of full production GO',
                                 'Exact exchange order ID and fill readback with recovery after restart'],
        'warning':'Production GO and pilot execution remain blocked. Simulated crash PASS is not a real WEEX crash test.'}
path=R/'weex_final_release_decision_latest.json'
tmp=path.with_suffix('.tmp')
tmp.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
os.replace(tmp,path)
print(json.dumps(report,ensure_ascii=False))
