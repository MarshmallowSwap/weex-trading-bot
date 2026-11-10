"""One-way, stopped-only switch to 20 USDT gross TP; backup config."""
import json,os,shutil
from pathlib import Path
import live_control
r=Path(__file__).resolve().parent
assert live_control.state(r)['mode']=='STOPPED','LIVE_NOT_STOPPED'
p=r/'weex_ai_risk_config.json'
c=json.loads(p.read_text(encoding='utf-8'))
assert c['execution']['enabled'] is False and c['execution']['mode']=='PRETRADE'
assert c['strategySettings']['tpMode']=='fixed'
a=c['strategySettings'];f=c['telegramSettings']['fixedProfit']
assert str(a['targetNetProfitUSDT']) in ('15','15.0','20','20.0')
assert str(f['targetNetProfitUSDT']) in ('15','15.0','20','20.0')
backup=r/'weex_ai_risk_config.before_gross_tp20.json'
if not backup.exists():shutil.copy2(p,backup)
a['targetNetProfitUSDT']=20.0
a['tpAccountingMode']='GROSS_BEFORE_COSTS'
f['targetNetProfitUSDT']=20.0
f['reference']='gross_price_pnl_before_entry_exit_fees_slippage_and_funding'
c['execution']['enabled']=False
c['execution']['mode']='PRETRADE'
tmp=p.with_suffix('.tmp')
tmp.write_text(json.dumps(c,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
os.replace(tmp,p)
assert live_control.state(r)['mode']=='STOPPED'
print('TP_GROSS_20_CONFIGURED')
print('BACKUP_EXISTS',backup.exists())
print('EXECUTION_ENABLED',c['execution']['enabled'])
print('MODE',live_control.state(r)['mode'])
print('ACCOUNTING',live_control.configuration(r)[0]['strategySettings']['tpAccountingMode'])
