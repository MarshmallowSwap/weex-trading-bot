"""One-time offline strategy floor migration to 100x. No API writes."""
from pathlib import Path
import json,os,hashlib
import live_control
R=Path(__file__).resolve().parent
assert live_control.state(R)['mode']=='STOPPED'
manifest=json.loads((R/'live_release_manifest.json').read_text(encoding='utf-8'))
assert all(hashlib.sha256((R/f).read_bytes()).hexdigest()==h for f,h in manifest['sha256'].items() if f!='market_agents_rotating.py')
cfgfile=R/'weex_ai_risk_config.json'
cfg=json.loads(cfgfile.read_text(encoding='utf-8'))
assert cfg['risk']['minimumLeverage']==50
assert cfg['risk']['leveragePreference']=='maximum_settable_cross_minimum_50'
assert cfg['execution']['enabled'] is False and cfg['execution']['mode']=='PRETRADE'
replacements={
 'weex_ai_universe.py':[('MIN_LEVERAGE=50','MIN_LEVERAGE=100')],
 'weex_max_leverage.py':[('MINIMUM=Decimal(50)','MINIMUM=Decimal(100)'),
 ('reference_price,minimum=50,cost_usdt=None','reference_price,minimum=100,cost_usdt=None'),
 ('MAXIMUM_LEVERAGE_FIRST_MINIMUM_50','MAXIMUM_LEVERAGE_FIRST_MINIMUM_100'),
 ('LEVERAGE_50_OR_HIGHER','LEVERAGE_100_OR_HIGHER')],
 'weex_lifecycle.py':[('LEVERAGE_BELOW_50','LEVERAGE_BELOW_100'),
 ("<50:raise ValueError", "<100:raise ValueError"),
 ("Decimal(50),dec(cfg['risk'].get('minimumLeverage',50))","Decimal(100),dec(cfg['risk'].get('minimumLeverage',100))")],
 'weex_simple_bot.py':[('if not pilot and leverage<50:','if not pilot and leverage<100:'),
 ('LEVERAGE_BELOW_50','LEVERAGE_BELOW_100'),
 ("minimum=cfg['risk'].get('minimumLeverage',50)","minimum=cfg['risk'].get('minimumLeverage',100)")],
 'weex_runtime_preflight.py':[("minimum=cfg['risk'].get('minimumLeverage',50)","minimum=cfg['risk'].get('minimumLeverage',100)")],
 'live_control.py':[("'minimumLeverage':str(cfg['risk'].get('minimumLeverage',50))","'minimumLeverage':str(cfg['risk'].get('minimumLeverage',100))")],
 'telegram_button_menu.py':[("config['risk'].get('minimumLeverage',50)","config['risk'].get('minimumLeverage',100)")],
 'weex_account_setup_audit.py':[('MAXIMUM_LEVERAGE_FIRST_MINIMUM_50','MAXIMUM_LEVERAGE_FIRST_MINIMUM_100'),
 ('Maximum permitted leverage >=50','Maximum permitted leverage >=100')],
 'market_agents_rotating.py':[('BATCH=40','BATCH=16')],
 'test_weex_max_leverage.py':[
 ('def test_floor_50_cannot_be_lowered_by_configuration','def test_floor_100_cannot_be_lowered_by_configuration'),
 ('50_OR_HIGHER','100_OR_HIGHER'),
 ("'maxLeverage':49},minimum=1","'maxLeverage':99},minimum=1"),
 ('never_below_50','never_below_100'),
 ('below_50','below_100'),
 ("plan['requestedLeverage']='49'","plan['requestedLeverage']='99'"),
 ('LEVERAGE_BELOW_50','LEVERAGE_BELOW_100')],

}
new={}
for file,changes in replacements.items():
    path=R/file
    body=path.read_text(encoding='utf-8')
    for old,value in changes:
        assert old in body,(file,old)
        body=body.replace(old,value)
    compile(body,file,'exec')
    new[file]=body
for file,body in new.items():
    (R/file).write_text(body,encoding='utf-8')
cfg['risk']['minimumLeverage']=100
cfg['risk']['leveragePreference']='maximum_settable_cross_minimum_100'
tmp=cfgfile.with_suffix('.floor100.tmp')
tmp.write_text(json.dumps(cfg,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
os.replace(tmp,cfgfile)
assert live_control.state(R)['mode']=='STOPPED'
print(json.dumps({'status':'MIGRATED_FLOOR_100X','changedFiles':sorted(new),'automaticTrading':'STOPPED','exchangeOrderWrites':0}))
