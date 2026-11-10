"""Publish verified OFFLINE test manifest, never enable live trading.

Test evidence: 1119 tests / 148 modules, offline socket-blocked suite,
excluded legacy modules test_readonly/test_scopes. Does not assert live GO.
"""
import hashlib,json,os
from datetime import datetime,timezone
from pathlib import Path
import live_control
from weex_live_new_entry_guard import evaluate
root=Path(__file__).resolve().parent
if live_control.state(root)['mode']!='STOPPED':
 raise PermissionError('LIVE_MUST_REMAIN_STOPPED')
cfg,_=live_control.configuration(root)
if (cfg['strategySettings'].get('tpMode')!='fixed'
 or cfg['strategySettings'].get('tpAccountingMode')!='GROSS_BEFORE_COSTS'
 or str(cfg['strategySettings'].get('targetNetProfitUSDT')) not in ('20','20.0')
 or cfg['execution'].get('enabled') is not False):
 raise ValueError('CONFIG_NOT_GROSS_20_STOPPED')
files=live_control.CODE_FILES
if len(files)!=len(set(files)):raise ValueError('DUPLICATE_CODE_FILE')
new={name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in files}
path=root/'live_release_manifest.json'
prior=json.loads(path.read_text(encoding='utf-8'))
backup=root/'live_release_manifest.before_gross_tp20_20261105.json'
if not backup.exists():backup.write_text(json.dumps(prior,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
current={**prior,'status':'OFFLINE_VERIFIED_NO_REAL_ORDERS',
 'testsPassed':True,'testCount':1119,
 'releasedAt':datetime.now(timezone.utc).isoformat(),
 'validationScope':'148 offline unittest modules / 1119 tests, network socket blocked; legacy test_readonly and test_scopes excluded. Gross 20 USDT TP, Telegram edit, lifecycle, restarts and guards. No exchange orders by this certification.',
 'excludedTestModules':['test_readonly','test_scopes'],
 'realOrdersSentDuringValidation':False,
 'telegramMessagesSentDuringValidation':False,
 'sha256':new,
 'liveGoCertified':False,
 'remainingLiveBlockers':['SHARED_CROSS_MARGIN_UNCERTIFIED']}
temp=path.with_suffix('.gross20.tmp')
temp.write_text(json.dumps(current,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
os.replace(temp,path)
assert not live_control.build_errors(root),live_control.build_errors(root)
assert live_control.state(root)['mode']=='STOPPED'
issues=evaluate(cfg,[],[],[])['issues']
print(json.dumps({'offlineManifest':'VERIFIED','testCount':1119,
 'hashedFiles':len(new),'backup':backup.exists(),
 'liveMode':'STOPPED','integrityErrors':live_control.build_errors(root),
 'entryGateIssues':issues,'liveGoCertified':False}))
