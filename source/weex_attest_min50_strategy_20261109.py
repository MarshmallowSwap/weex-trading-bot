"""Attest the reviewed 50x strategy floor; never arm production."""
import hashlib,json,os,subprocess,sys
from pathlib import Path
from datetime import datetime,timezone
import live_control

R=Path(__file__).resolve().parent
mfile=R/'live_release_manifest.json'
m=json.loads(mfile.read_text(encoding='utf-8'))
assert m['status']=='OFFLINE_VERIFIED_NO_REAL_ORDERS' and m['testsPassed'] is True
assert set(m['sha256'])==set(live_control.CODE_FILES)
changed=sorted(f for f,h in m['sha256'].items()
 if hashlib.sha256((R/f).read_bytes()).hexdigest()!=h)
expected=sorted(['live_control.py','telegram_button_menu.py','weex_ai_universe.py',
 'weex_lifecycle.py','weex_max_leverage.py','weex_runtime_preflight.py',
 'weex_simple_bot.py'])
assert changed==expected,(changed,expected)
assert live_control.state(R)['mode']=='STOPPED'
cfg=json.loads((R/'weex_ai_risk_config.json').read_text(encoding='utf-8'))
assert cfg['risk']['minimumLeverage']==50
assert cfg['risk']['leveragePreference']=='maximum_settable_cross_minimum_50'
assert cfg['risk']['belowMinimumLeverageAction']=='skip_trade'
assert cfg['risk']['discretionaryLeverageReduction'] is False
assert cfg['risk']['leverageSizingPriority']=='maximize_leverage_then_fit_quantity'
assert cfg['execution']['enabled'] is False and cfg['execution']['mode']=='PRETRADE'
scan=json.loads((R/'universe_latest.json').read_text(encoding='utf-8'))
assert scan['minLeverageFilter']==50 and scan['count']==len(scan['symbols'])
assert scan['count']>0 and all(x['maxLeverageAdvertised']>=50 for x in scan['symbols'])
tests=subprocess.run([sys.executable,'-m','unittest','-q',
 'test_weex_strategy_floor50_20261109','test_weex_max_leverage',
 'test_weex_lifecycle','test_weex_pretrade_regression',
 'test_max_cross_leverage_resolver','test_weex_trading_modes',
 'test_weex_live_new_entry_guard','test_live_control_release_gate',
 'test_live_release_gate'],cwd=R,capture_output=True,text=True,timeout=90)
assert tests.returncode==0 and 'Ran 111 tests' in tests.stderr,tests.stderr[-1000:]
for f in changed:m['sha256'][f]=hashlib.sha256((R/f).read_bytes()).hexdigest()
m['strategyMinimum50x']={'certifiedAt':datetime.now(timezone.utc).isoformat(),
 'minimumAdvertisedLeverage':50,'highestVerifiedLeverageStillPreferred':True,
 'eligibleUniverseCount':scan['count'],'regressionTestsPassed':111,
 'realOrderWrites':0,'liveEnabled':False}
m['validationScope']=m.get('validationScope','')+(
 ' Strategy eligibility floor lowered to 50x; maximum verified permitted'
 ' leverage still selected with account risk-tier and step/fee guards.'
 ' Public WEEX universe refreshed and 111 regressions passed. No live orders.')
tmp=mfile.with_suffix('.tmp')
tmp.write_text(json.dumps(m,indent=2)+'\n',encoding='utf-8');os.replace(tmp,mfile)
assert live_control.build_errors(R)==[],live_control.build_errors(R)
print(json.dumps({'status':'ATTESTED','minimumLeverage':50,
 'eligiblePairs':scan['count'],'tests':111,
 'codeIntegrity':'PASS','tradingMode':live_control.state(R)['mode']}))
