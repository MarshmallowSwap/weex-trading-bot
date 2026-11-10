"""One-time, fail-closed migration from 125x strategy floor to 50x.
No live switch activation, credential reads, HTTP calls, or exchange orders.
"""
from pathlib import Path
import json,hashlib,os
import live_control

R=Path(__file__).resolve().parent
assert live_control.state(R)['mode']=='STOPPED'
assert live_control.build_errors(R)==[]
paths={
 'weex_max_leverage.py':[
  ('MINIMUM=Decimal(75)','MINIMUM=Decimal(50)'),
  ('reference_price,minimum=75,cost_usdt=None','reference_price,minimum=50,cost_usdt=None'),
  ("'policy':'MAXIMUM_LEVERAGE_FIRST_MINIMUM_75'","'policy':'MAXIMUM_LEVERAGE_FIRST_MINIMUM_50'"),
  ("raise ValueError('NO_VALID_QUANTITY_AT_LEVERAGE_75_OR_HIGHER')","raise ValueError('NO_VALID_QUANTITY_AT_LEVERAGE_50_OR_HIGHER')")],
 'weex_ai_universe.py':[('MIN_LEVERAGE=100','MIN_LEVERAGE=50')],
 'weex_lifecycle.py':[
  ("if dec(p['requestedLeverage'])<75:raise ValueError('LEVERAGE_BELOW_75')","if dec(p['requestedLeverage'])<50:raise ValueError('LEVERAGE_BELOW_50')"),
  ("max(Decimal(75),dec(cfg['risk'].get('minimumLeverage',75)))","max(Decimal(50),dec(cfg['risk'].get('minimumLeverage',50)))")],
 'weex_simple_bot.py':[
  ("if not pilot and leverage<75:raise ValueError('LEVERAGE_BELOW_75')","if not pilot and leverage<50:raise ValueError('LEVERAGE_BELOW_50')"),
  ("minimum=cfg['risk'].get('minimumLeverage',75)","minimum=cfg['risk'].get('minimumLeverage',50)")],
 'weex_runtime_preflight.py':[
  ("minimum=cfg['risk'].get('minimumLeverage',75)","minimum=cfg['risk'].get('minimumLeverage',50)")],
 'weex_account_setup_audit.py':[
  ("'leveragePolicy':'MAXIMUM_LEVERAGE_FIRST_MINIMUM_75'","'leveragePolicy':'MAXIMUM_LEVERAGE_FIRST_MINIMUM_50'"),
  ('Maximum permitted leverage >=75','Maximum permitted leverage >=50')],
 'live_control.py':[("'minimumLeverage':str(cfg['risk'].get('minimumLeverage',75))","'minimumLeverage':str(cfg['risk'].get('minimumLeverage',50))")],
 'telegram_button_menu.py':[("config['risk'].get('minimumLeverage',75)","config['risk'].get('minimumLeverage',50)")],
 'test_weex_max_leverage.py':[
  ("def test_floor_75_cannot_be_lowered_by_configuration(self):","def test_floor_50_cannot_be_lowered_by_configuration(self):"),
  ("'75_OR_HIGHER'","'50_OR_HIGHER'"),
  ("'maxLeverage':50},minimum=1","'maxLeverage':49},minimum=1"),
  ("def test_minimum_quantity_can_require_lower_valid_tier_but_never_below_75(self):","def test_minimum_quantity_can_require_lower_valid_tier_but_never_below_50(self):"),
  ("def test_executor_rejects_prepared_plan_below_75(self):","def test_executor_rejects_prepared_plan_below_50(self):"),
  ("plan['requestedLeverage']='74'","plan['requestedLeverage']='49'"),
  ("'LEVERAGE_BELOW_75'","'LEVERAGE_BELOW_50'")]
}
cfgpath=R/'weex_ai_risk_config.json'
cfg=json.loads(cfgpath.read_text(encoding='utf-8'))
assert cfg['risk']['minimumLeverage']==125
assert cfg['risk']['leveragePreference']=='maximum_settable_cross_minimum_125'
assert cfg['execution']['enabled'] is False and cfg['execution']['mode']=='PRETRADE'
for filename,replacements in paths.items():
    data=(R/filename).read_text(encoding='utf-8')
    for old,new in replacements:
        expected=2 if filename=='weex_lifecycle.py' and old.startswith('max(Decimal') else 1
        assert data.count(old)==expected,(filename,old,data.count(old))
        data=data.replace(old,new)
    compile(data,filename,'exec')
    (R/filename).write_text(data,encoding='utf-8')
cfg['risk']['minimumLeverage']=50
cfg['risk']['leveragePreference']='maximum_settable_cross_minimum_50'
config_tmp=cfgpath.with_suffix('.migration.tmp')
config_tmp.write_text(json.dumps(cfg,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
os.replace(config_tmp,cfgpath)
assert live_control.state(R)['mode']=='STOPPED'
print(json.dumps({'status':'MIN_LEVERAGE_50_MIGRATED','fileCount':len(paths),
 'minimumLeverage':50,'mode':'STOPPED','exchangeWrites':0}))
