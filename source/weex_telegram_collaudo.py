"""Reusable, read-only WEEX Telegram COLLAUDO diagnostic.

Never starts/stops trading, changes config, sends an order, or modifies release
checks. Can run as often as requested. An incomplete result remains NO_GO.
"""
import json,subprocess,sys,threading,time,hashlib,os
from datetime import datetime,timezone
from pathlib import Path
import live_control

ROOT=Path(__file__).resolve().parent
_MUTEX=threading.Lock()
TIMEOUT=50

def _json_command(name,root,timeout=25):
    path=Path(root)/name
    if path.parent.resolve()!=Path(root).resolve() or not path.is_file():
        return {'error':'SCRIPT_MISSING'}
    try:
        p=subprocess.run([sys.executable,'-B',str(path)],cwd=root,
                         capture_output=True,text=True,timeout=timeout)
        if p.returncode!=0:return {'error':'SCRIPT_NONZERO','exitCode':p.returncode}
        return json.loads(p.stdout.strip().splitlines()[-1])
    except (subprocess.TimeoutExpired,ValueError,IndexError,OSError):
        return {'error':'SCRIPT_TIMEOUT_OR_INVALID_OUTPUT'}

def diagnose(root=ROOT,probe=_json_command):
    root=Path(root)
    begun=datetime.now(timezone.utc).isoformat()
    result={'checkedAt':begun,'mode':'READ_ONLY_COLLAUDO','exchangeWrites':0,
            'productionOrdersAuthorized':False,'tradingEnabledByCollaudo':False}
    # Keep fail-closed even if user invokes COLLAUDO while the bot is already live.
    try:
        switch=live_control.state(root)
        cfg=json.loads((root/'weex_ai_risk_config.json').read_text(encoding='utf-8'))
        result['switch']=switch['mode']
        result['pretradeConfig']=cfg.get('execution',{}).get('enabled') is False and cfg.get('execution',{}).get('mode')=='PRETRADE'
        result['integrityErrors']=live_control.build_errors(root)
        # Refresh the actual GET-only prerequisites in dependency order,
        # otherwise refreshing only live_release_gate.py would demote a valid
        # release solely because its input reconciliation expired.
        if (root/'weex_collaudo_refresh_readonly.py').is_file():
            if switch['mode']=='STOPPED' and result['pretradeConfig'] and not result['integrityErrors']:
                fresh=probe('weex_collaudo_refresh_readonly.py',root,110)
                result['gateRefresh']='PASS' if fresh.get('status')=='REFRESHED_READ_ONLY' else 'FAILED'
                result['refreshSteps']=fresh.get('steps',[])
            else:
                result['gateRefresh']='SKIPPED_NOT_DISARMED_OR_INTEGRITY'
        else:
            result['gateRefresh']='SKIPPED_NO_REFRESH_SCRIPT'
        gate=json.loads((root/'live_release_gate_latest.json').read_text(encoding='utf-8'))
        result['gate']=gate.get('gate','UNKNOWN')
        result['gatePassed']=gate.get('passed',0)
        result['gateTotal']=gate.get('total',0)
        result['gateBlockers']=[k for k,v in (gate.get('checks') or {}).items() if v is not True]
        restart_evidence=(gate.get('evidenceScopes') or {}).get('restart') or {}
        result['crashEvidenceReason']=(restart_evidence.get('reason','NOT_CERTIFIED')
            if isinstance(restart_evidence,dict) else 'NOT_CERTIFIED')
        result['gateAgeSeconds']=int(time.time()-datetime.fromisoformat(gate['checkedAt'].replace('Z','+00:00')).timestamp())
        result['gateFresh']=0<=result['gateAgeSeconds']<=600
        # Offline OS-crash test uses ONLY a temporary DB and a durable fake exchange.
        # Do not run it on a machine with an armed trading switch.
        if switch['mode']=='STOPPED' and result['pretradeConfig'] and not result['integrityErrors']:
            result['crashProbe']=probe('weex_worker_crash_probe_test_20261109.py',root,35)
        else:
            result['crashProbe']={'status':'SKIPPED_NOT_DISARMED_OR_INTEGRITY'}
        # Authenticated read-only account snapshot; no live_worker.py invocation,
        # because its recovery path may manage existing protective orders.
        result['account']=probe('weex_final_live_status_readonly_20261109.py',root,25)
        account=result['account']
        result['accountClear']=(isinstance(account,dict) and not account.get('error')
                                and account.get('positions')==0
                                and account.get('orders')==0 and account.get('conditional')==0
                                and account.get('unresolvedWrites')==[]
                                and account.get('integrity')==[])
        crash=result['crashProbe']
        result['localCrashPassed']=(crash.get('status')=='PASS' and
                                   crash.get('childExitCode')==79 and
                                   crash.get('duplicateEntries')==0 and
                                   crash.get('recoveredState')=='PROTECTED' and
                                   crash.get('networkRequests')==0 and crash.get('liveOrders')==0)
        result['status']='CHECKS_PASS_NO_REAL_ACTIVATION' if all((
            result['accountClear'],result['localCrashPassed'],
            result['gateFresh'],result['pretradeConfig'],
            result['gateRefresh'] in ('PASS','SKIPPED_NO_REFRESH_SCRIPT'),
            result['switch']=='STOPPED',not result['integrityErrors']
        )) else 'ATTENTION'
        result['realCrashCertified']=False
        result['nextAction']='SUPERVISED_REAL_WORKER_TEST_REQUIRES_SEPARATE_SCOPE' if not result['gate']=='GO' else 'EXPLICIT_LIVE_START_REQUIRED'
    except Exception as exc:
        result['status']='ERROR'
        result['errorType']=type(exc).__name__
    # Atomic result file; never overwrite gate/manifest/configuration.
    target=root/'weex_telegram_collaudo_latest.json'
    try:
        t=target.with_suffix('.tmp')
        t.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
        os.replace(t,target)
    except OSError:
        pass
    return result

def format_telegram(result):
    account=result.get('account') or {}
    test=result.get('crashProbe') or {}
    blockers=result.get('gateBlockers') or []
    b=', '.join(blockers[:3]) if blockers else 'nessuno'
    return ('WEEX | COLLAUDO\n'
        f"Esito: {result.get('status','ERROR')}\n"
        f"Controlli produzione: {result.get('gatePassed','?')}/{result.get('gateTotal','?')} ({result.get('gate','UNKNOWN')})\n"
        f"Conto: posizioni {account.get('positions','?')}, ordini {account.get('orders','?')}, condizionali {account.get('conditional','?')}\n"
        f"Crash locale: {'PASS' if result.get('localCrashPassed') else test.get('status','NON VERIFICATO')}\n"
        f"Integrita: {'PASS' if not result.get('integrityErrors') else 'ERRORE'}\n"
        f"Aggiornamento verifiche: {result.get('gateRefresh','NON ESEGUITO')}\n"
        f"Prova crash reale: {result.get('crashEvidenceReason','NON CERTIFICATA')}\n"
        f"Blocco: {b}\n"
        'Nessun ordine inviato. COLLAUDO non avvia il trading reale.\n'
        'Il test sul conto reale richiede una procedura supervisionata separata.')

def run_telegram(send,token,chat,root=ROOT):
    if not _MUTEX.acquire(blocking=False):
        send(token,'sendMessage',{'chat_id':chat,'text':'COLLAUDO gia in esecuzione. Nessun ordine inviato.'})
        return
    try:
        result=diagnose(root)
        send(token,'sendMessage',{'chat_id':chat,'text':format_telegram(result)})
    finally:_MUTEX.release()

def start_telegram(send,token,chat,root=ROOT):
    # Reserve synchronously to prevent simultaneous duplicate commands.
    if not _MUTEX.acquire(blocking=False):
        return False
    def task():
        try:
            result=diagnose(root)
            send(token,'sendMessage',{'chat_id':chat,'text':format_telegram(result)})
        finally:_MUTEX.release()
    try:
        threading.Thread(target=task,name='weex-collaudo-readonly',daemon=True).start()
        return True
    except BaseException:
        _MUTEX.release()
        raise

if __name__=='__main__':
    print(format_telegram(diagnose()))
