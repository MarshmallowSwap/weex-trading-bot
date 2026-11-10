"""Certify 100x strategy floor after verified API universe refresh. No trading writes."""
import hashlib,json,os,subprocess,sys
from pathlib import Path
from datetime import datetime,timezone
import live_control
R=Path(__file__).resolve().parent
manifest_path=R/'live_release_manifest.json'
m=json.loads(manifest_path.read_text(encoding='utf-8'))
assert m['status']=='OFFLINE_VERIFIED_NO_REAL_ORDERS' and m['testsPassed'] is True
assert set(m['sha256'])==set(live_control.CODE_FILES)
changed=sorted(f for f,h in m['sha256'].items()
 if hashlib.sha256((R/f).read_bytes()).hexdigest()!=h)
expected=sorted(['telegram_button_menu.py','live_control.py','weex_lifecycle.py',
 'weex_runtime_preflight.py','weex_simple_bot.py','weex_max_leverage.py','weex_ai_universe.py'])
assert changed==expected,(changed,expected)
assert live_control.state(R)['mode']=='STOPPED'
cfg=json.loads((R/'weex_ai_risk_config.json').read_text(encoding='utf-8'))
assert cfg['risk']['minimumLeverage']==100
assert cfg['risk']['leveragePreference']=='maximum_settable_cross_minimum_100'
assert cfg['risk']['belowMinimumLeverageAction']=='skip_trade'
assert cfg['risk']['discretionaryLeverageReduction'] is False
assert cfg['execution']['enabled'] is False and cfg['execution']['mode']=='PRETRADE'
u=json.loads((R/'universe_latest.json').read_text(encoding='utf-8'))
assert u['minLeverageFilter']==100 and u['count']==108
assert len(u['symbols'])==u['count']
assert all(x['maxLeverageAdvertised']>=100 for x in u['symbols'])
modules=['test_weex_strategy_floor100_20261109','test_weex_max_leverage',
 'test_weex_lifecycle','test_weex_pretrade_regression',
 'test_max_cross_leverage_resolver','test_weex_trading_modes',
 'test_weex_live_new_entry_guard','test_live_control_release_gate',
 'test_live_release_gate','test_weex_scan_recovery_headroom_20261109']
tests=subprocess.run([sys.executable,'-m','unittest','-q',*modules],
 cwd=R,capture_output=True,text=True,timeout=90)
assert tests.returncode==0 and 'Ran 117 tests' in tests.stderr,tests.stderr[-1000:]
for f in changed:m['sha256'][f]=hashlib.sha256((R/f).read_bytes()).hexdigest()
m['strategyMinimum100x']={'certifiedAt':datetime.now(timezone.utc).isoformat(),
 'eligibleUniverseCount':108,'maximumLeverageStillPreferred':True,
 'minimumAdvertisedLeverage':100,'regressionTestsPassed':117,
 'realOrderWrites':0,'liveEnabled':False}
m['validationScope']=m.get('validationScope','')+(
 ' Eligibility changed to min 100x verified exchange max leverage.'
 ' Updated universe 108 pairs, 80 removed compared with 50x.'
 ' Higher verified exchange maximum is still selected and account readback'
 ' remains required at entry. 117 offline tests passed; no trading orders.')
tmp=manifest_path.with_suffix('.tmp')
tmp.write_text(json.dumps(m,indent=2)+'\n',encoding='utf-8')
os.replace(tmp,manifest_path)
assert live_control.build_errors(R)==[],live_control.build_errors(R)
print(json.dumps({'status':'ATTESTED_MINIMUM_100X','universe':108,
 'testsPassed':117,'integrity':'PASS','mode':live_control.state(R)['mode']}))
