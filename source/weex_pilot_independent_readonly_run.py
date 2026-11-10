"""Existing WEEX account: independent isolated pilot readiness report, GET-only."""
import json,os
from pathlib import Path
from datetime import datetime,timezone
from weex_existing_account_1x_pilot_audit import journal_inventory
from weex_isolated_pilot_gate import read as observe
from weex_pilot_independent_preflight import assess
import live_control

R=Path(__file__).resolve().parent

def run():
    switch=live_control.state(R)
    if switch['mode']!='STOPPED':raise PermissionError('MAIN_BOT_RUNNING')
    pilot=json.loads((R/'weex_live_1x_pilot_config.json').read_text())
    account=observe()
    journal=journal_inventory(R/'weex_isolated_pilot.sqlite3')
    result=assess(pilot,account,journal,main_switch=switch['mode'],
                  integrity_errors=live_control.build_errors(R))
    result.update({'checkedAt':datetime.now(timezone.utc).isoformat(),
                   'pilotJournal':journal,'indicativeOrder':account.get('indicativeOrder'),
                   'productionLiveSwitch':switch['mode'],
                   'originalProductionGate':json.loads((R/'live_release_gate_latest.json').read_text()).get('gate'),
                   'exchangeWrites':0})
    target=R/'weex_pilot_independent_preflight_latest.json'
    tmp=target.with_suffix('.tmp')
    tmp.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    os.replace(tmp,target)
    return result

if __name__=='__main__':
    print(json.dumps(run(),ensure_ascii=False))
