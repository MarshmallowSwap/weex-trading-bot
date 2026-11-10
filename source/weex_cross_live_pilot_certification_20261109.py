"""Scoped real-account CROSS 1x pilot certification. No exchange writes.
One fully reconciled open-close lifecycle does NOT certify crash/restart of
the general automatic bot or full historical quote accounting.
"""
import json,os
from pathlib import Path
from decimal import Decimal as D
from datetime import datetime,timezone
import live_control
ROOT=Path(__file__).resolve().parent
trial=json.loads((ROOT/'weex_cross_one_shot_real_pilot_20261109.json').read_text())
proof=json.loads((ROOT/'weex_cross_one_shot_real_independent_audit_20261109.json').read_text())
verified=(trial.get('stage')=='CROSS_PILOT_CLOSED_AND_VERIFIED'
 and proof.get('environment')=='WEEX_REAL_ACCOUNT'
 and proof.get('allIndependentChecksPassed') is True
 and trial.get('entryPostCount')==1 and trial.get('closePostCount')==1
 and trial.get('stopCancellationRequests')==0
 and all(trial.get(k)==proof.get(k) for k in ('entryOrderId','closeOrderId','stopAlgoId'))
 and live_control.state(ROOT)['mode']=='STOPPED' and not live_control.build_errors(ROOT))
net=(D(proof['exitQuoteUSDT'])-D(proof['entryQuoteUSDT'])
     -D(proof['entryReportedCommission'])-D(proof['exitReportedCommission']))
report={'checkedAt':datetime.now(timezone.utc).isoformat(),
 'scope':'ONE_ETHUSDT_CROSS_1X_REAL_ACCOUNT_ORDER_CYCLE',
 'livePilotCycleCertified':verified,
 'livePilotEntryCertified':verified and proof['entryVerified'],
 'livePilotAttachedStopCertified':verified and trial['stopVerified'],
 'livePilotReduceOnlyExitCertified':verified and proof['reduceOnlyCloseVerified'],
 'livePilotExactPositionCloseCertified':verified and proof['accountFlatVerified'],
 'livePilotStopTerminalCertified':verified and proof['stopTerminalVerified'],
 'positionsAndPendingOrdersZero':proof['accountFlatVerified'],
 'netUSDTFromFillsAndCommission':str(net),
 'quoteAccountingFullHistoryCertified':False,
 'automaticBotCrashRestartCertified':False,
 'generalBotReleaseAuthorized':False,
 'newLiveOrderAuthorized':False,
 'realOrdersAlreadySubmitted':2,
 'sourceFiles':['weex_cross_one_shot_real_pilot_20261109.json',
                'weex_cross_one_shot_real_independent_audit_20261109.json'],
 'botMode':live_control.state(ROOT)['mode'],'exchangeWrites':0}
path=ROOT/'weex_cross_live_pilot_certification_20261109.json'
temp=path.with_suffix('.tmp');temp.write_text(json.dumps(report,indent=2));os.replace(temp,path)
print(json.dumps(report))
