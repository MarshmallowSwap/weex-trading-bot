"""WEEX controlled crash-injection switch (OFFLINE ONLY).

Does not arm production or send exchange orders. The only allowed target is the
persistent lifecycle with a local simulated exchange, using a fresh temp dir.
"""
import json,os,subprocess,sys
from pathlib import Path
from datetime import datetime,timezone
import live_control
from weex_full_lifecycle_os_crash_drill import run
ROOT=Path(__file__).resolve().parent
CONFIG=ROOT/'weex_CRASH_INJECTION_OFFLINE_CONTROL_20261109.json'
REPORT=ROOT/'weex_CRASH_INJECTION_OFFLINE_RESULT_20261109.json'
STAGES=['ENTRY_BEFORE_SEND','ENTRY_AFTER_SEND','TP_BEFORE_SEND','TP_AFTER_SEND']
def save(path,obj):
 tmp=path.with_suffix('.tmp')
 tmp.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 os.replace(tmp,path)
def activate():
 if live_control.state(ROOT)['mode']!='STOPPED' or live_control.build_errors(ROOT):
  raise PermissionError('PRODUCTION_MUST_REMAIN_STOPPED_WITH_VALID_MANIFEST')
 cfg=json.loads((ROOT/'weex_ai_risk_config.json').read_text(encoding='utf-8'))
 if cfg.get('execution',{}).get('enabled') is not False or cfg['execution'].get('mode')!='PRETRADE':
  raise PermissionError('LIVE_EXECUTION_MUST_BE_DISABLED')
 settings={'createdAt':datetime.now(timezone.utc).isoformat(),
  'enabled':True,'environment':'OFFLINE_SIMULATED_EXCHANGE_ONLY',
  'gateway':'DURABLE_FAKE_EXCHANGE','scenarioNames':STAGES,
  'liveExchangeAccess':False,'realOrdersAllowed':False,
  'productionConfigChanged':False,'productionTradingSwitchChanged':False}
 save(CONFIG,settings)
 return settings
def test():
 if not CONFIG.exists():raise PermissionError('CRASH_CONTROL_NOT_ENABLED')
 setting=json.loads(CONFIG.read_text(encoding='utf-8'))
 if (setting.get('enabled') is not True or setting.get('environment')!='OFFLINE_SIMULATED_EXCHANGE_ONLY'
     or setting.get('scenarioNames')!=STAGES or setting.get('liveExchangeAccess') is not False
     or setting.get('realOrdersAllowed') is not False):
  raise PermissionError('OFFLINE_INJECTION_POLICY_INVALID')
 if live_control.state(ROOT)['mode']!='STOPPED':raise PermissionError('LIVE_RUNNING')
 result=run()
 passed=(result['status']=='FULL_LIFECYCLE_OS_CRASH_SIMULATED_EXCHANGE'
    and result['realWEEXCrashTested'] is False and result['exchangeWrites']==0
    and len(result['results'])==4 and
    [x['crashPoint'] for x in result['results']]==STAGES
    and all(x['noDuplicateWrite'] for x in result['results']))
 out={'checkedAt':datetime.now(timezone.utc).isoformat(),
      'offlineInjectionEnabled':True,'testPassed':passed,
      'allFourCrashPoints':result['results'],
      'realExchangeCrashCertified':False,
      'productionReleaseGateCertified':False,'exchangeWrites':0,
      'botState':live_control.state(ROOT)['mode'],
      'manifestErrors':live_control.build_errors(ROOT)}
 save(REPORT,out)
 if not passed or out['manifestErrors']:raise AssertionError('OFFLINE_DRILL_FAILED')
 return out
if __name__=='__main__':
 activated=activate()
 outcome=test()
 print(json.dumps({'control':str(CONFIG),'report':str(REPORT),
  'enabled':activated['enabled'],'environment':activated['environment'],
  'testsPassed':len(outcome['allFourCrashPoints']),
  'offlinePassed':outcome['testPassed'],
  'realExchangeCrashCertified':False,'exchangeWrites':0,
  'bot':outcome['botState']}))
