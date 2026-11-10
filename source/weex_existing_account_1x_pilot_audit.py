"""Existing-account isolated 1x pilot readiness snapshot. No order submission.

Preserves main WEEX account, STOPPED switch, and existing local journals.
Requires exact current account readback and reports blockers without bypass.
"""
import json,sqlite3
from pathlib import Path
from datetime import datetime,timezone
from contextlib import closing
import live_control
from weex_isolated_pilot_gate import read as read_exchange

ROOT=Path(__file__).resolve().parent

def journal_inventory(path):
    path=Path(path)
    if not path.is_file():return {'state':'MISSING','records':None}
    with closing(sqlite3.connect('file:'+path.resolve().as_posix()+'?mode=ro',uri=True)) as c:
        tables={row[0] for row in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if 'pilot_v1' not in tables:return {'state':'INVALID_SCHEMA','records':None}
        records=c.execute('SELECT COUNT(*) FROM pilot_v1').fetchone()[0]
        dispatch=c.execute('SELECT COUNT(*) FROM pilot_dispatch_v1').fetchone()[0] if 'pilot_dispatch_v1' in tables else 0
        return {'state':'READ_ONLY','records':records,'dispatchRows':dispatch}

def assess_local(exchange,journal,switch):
    problems=list(exchange.get('issues') or [])
    if exchange.get('orderAuthorized') is not False:problems.append('EXCHANGE_AUDIT_NOT_FAIL_CLOSED')
    if switch!='STOPPED':problems.append('BOT_NOT_STOPPED')
    if journal['state']!='READ_ONLY':problems.append('PILOT_JOURNAL_UNAVAILABLE')
    if journal.get('records')!=0:problems.append('PILOT_JOURNAL_REQUIRES_REVIEW')
    if journal.get('dispatchRows',0)!=0:problems.append('PILOT_DISPATCH_REQUIRES_REVIEW')
    # User-selected pilot policy: no mandatory SL for this 1x, <=5 USDT
    # notional test. The independent upstream gate is left unchanged.
    # Lack of SL is explicitly disclosed, never represented as risk-free.
    stop_warning='PILOT_WITHOUT_STOP_LOSS_POSITION_CAN_REMAIN_EXPOSED'
    if 'PILOT_STOP_LOSS_NOT_VERIFIED' in problems:
        problems.remove('PILOT_STOP_LOSS_NOT_VERIFIED')
        warnings=[stop_warning]
    else:
        warnings=[]
    if 'REDUCE_ONLY_EXIT_NOT_VERIFIED' in problems:
        problems.append('NO_VERIFIED_EMERGENCY_CLOSE_PATH')
    return {'pilotExecutionAllowed':False,'readOnly':True,'existingAccount':True,
            'stopLossMandatoryForPilot':False,'warnings':warnings,
            'exchangeWrites':0,'blockers':sorted(set(problems)),
            'pilotJournal':journal,'exchangeIndicativeOrder':exchange.get('indicativeOrder')}

def run():
    if live_control.state(ROOT)['mode']!='STOPPED':raise PermissionError('BOT_NOT_STOPPED')
    exchange=read_exchange()
    journal=journal_inventory(ROOT/'weex_isolated_pilot.sqlite3')
    report=assess_local(exchange,journal,live_control.state(ROOT)['mode'])
    report['checkedAt']=datetime.now(timezone.utc).isoformat()
    dest=ROOT/'weex_existing_account_1x_pilot_latest.json'
    tmp=dest.with_suffix('.tmp')
    tmp.write_text(json.dumps(report,indent=2),encoding='utf-8')
    tmp.replace(dest)
    return report

if __name__=='__main__':print(json.dumps(run(),ensure_ascii=False))
