"""Convert dormant ETH pilot declaration to CROSS 1x, fail closed.

Does not change exchange symbolConfig, submit orders or activate execution.
Legacy transport still requires ISOLATED and must reject until migrated.
"""
import json,os
from pathlib import Path
from datetime import datetime,timezone
import live_control
R=Path(__file__).resolve().parent
p=R/'weex_live_1x_pilot_config.json'
cfg=json.loads(p.read_text(encoding='utf-8'))
main=json.loads((R/'weex_ai_risk_config.json').read_text(encoding='utf-8'))
if live_control.state(R)['mode']!='STOPPED':raise PermissionError('MAIN_NOT_STOPPED')
if main['risk']['marginModePreference'].lower()!='cross':raise PermissionError('MAIN_CROSS_NOT_SET')
if cfg['exchange']!='WEEX' or cfg['leverage']!=1 or cfg['marginMode'] not in ('ISOLATED','CROSS'):
 raise ValueError('UNRECOGNIZED_PILOT')
if cfg['executionEnabled'] or cfg['liveOrderSubmissionAllowed']:raise PermissionError('PILOT_IS_ACTIVE')
cfg['marginMode']='CROSS'
cfg['executionEnabled']=False
cfg['liveOrderSubmissionAllowed']=False
cfg['stopLossVerified']=False
cfg['reduceOnlyCloseVerified']=False
cfg['environment']='CROSS_1X_PILOT_MIGRATION_BLOCKED'
cfg['warning']=('CROSS margin can expose all available account collateral. '
 'Legacy isolated-only guards remain incompatible; no order authorization '
 'until exact CROSS preflight, ownership, close, and restart recovery tests.')
tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(cfg,indent=2)+'\n',encoding='utf-8');os.replace(tmp,p)
report={'checkedAt':datetime.now(timezone.utc).isoformat(),'mainMarginMode':'cross',
 'pilotMarginMode':'CROSS','pilotLeverage':1,
 'productionWrites':0,'liveOrdersAuthorized':False,
 'pilotExecutionEnabled':False,
 'blockingReason':'ISOLATED_ONLY_TRANSPORT_AND_OWNERSHIP_GUARDS_REQUIRE_MIGRATION'}
rp=R/'weex_cross_pilot_migration_latest.json';tp=rp.with_suffix('.tmp')
tp.write_text(json.dumps(report,indent=2)+'\n');os.replace(tp,rp)
print(json.dumps(report))
