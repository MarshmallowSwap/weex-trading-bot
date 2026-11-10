"""User-operated LIVE switch. Default STOPPED, persisted nonce-bound confirmation.

This module sends no exchange or Telegram requests. STOP gates new entries;
owned-position protection and reconciliation are independent of this switch.
"""
import hashlib,json,secrets,sqlite3,time
from contextlib import contextmanager
from datetime import datetime,timezone
from decimal import Decimal
from pathlib import Path

ROOT=Path(__file__).resolve().parent
CODE_FILES=('telegram_button_menu.py','telegram_cost_settings.py','weex_reconcile.py','weex_close_proof.py','live_test_once_preflight.py','weex_fill_alerts.py','weex_neutral_fill_card.py','weex_isolated_pilot_offline_journal.py','weex_isolated_pilot_transport_harness.py','weex_telegram_cleanup.py','weex_alert_archive.py','weex_alert_quality.py','weex_closed_quality.py','weex_quality_auditors.py','weex_position_reports.py','weex_position_cards.py','telegram_position_reports.py','weex_incidents.py','weex_read_recovery.py','weex_incident_supervisor.py','weex_service_health.py','run_autonomy_supervisor.ps1','weex_account_observation.py','weex_local_diagnostics.py','position_manager_integrated.py','position_readonly_adapter.py','weex_api_budget.py','monitor.py','weex_ai_signals.py','live_control.py','telegram_live_control.py','weex_live_worker.py','weex_lifecycle.py','weex_external_tp_adoption.py',
'weex_trading_modes.py','weex_trailing.py','weex_http_guard.py','weex_runtime_preflight.py','weex_simple_bot.py','weex_manual_position_ack.py',
            'weex_max_leverage.py','weex_capacity.py','orderbook_liquidity.py','market_agents.py',
            'weex_tp_pnl_preview.py','weex_live_new_entry_guard.py','weex_optional_stop_policy.py','weex_quote_semantics_readonly_probe.py','weex_tp_local_notsent_repair.py',
            'live_release_gate.py','account_reconciliation_point1.py','reconcile_recent_fills_readonly.py',
            'protection_coverage_v2.py','protection_pagination.py','protection_policy.py',
            'position_ownership_gate.py','weex_order_pagination.py','verified_order_state_sync.py',
            'preflight_verified.py','release_decision_bundle.py',
            'commands.py','run_integrated_position_audit.ps1','telegram_ai_fullmenu.py',
            'telegram_ai_settings.py','agents_status.py','agents_status_card.py','settings_card.py',
            'live_demo_alias_proof.json','weex_ai_universe.py','weex_execution_cycle.py','weex_agent_orchestrator.py','weex_autonomy_supervisor.py','agent_health.py','market_agents_rotating.py','weex_scan_data.py','weex_depth_evidence.py','weex_depth_autovalidation.py','weex_scan_notifications.py',
            'weex_real_worker_crash_evidence_gate.py','weex_telegram_collaudo.py',
            'weex_collaudo_refresh_readonly.py','weex_worker_crash_probe_test_20261109.py',
            'weex_final_live_status_readonly_20261109.py')

def timestamp():return datetime.now(timezone.utc).isoformat()
def connect(root=ROOT):
    c=sqlite3.connect(Path(root)/'live_control.sqlite3',timeout=20)
    c.row_factory=sqlite3.Row;c.execute('PRAGMA synchronous=FULL')
    c.executescript('''CREATE TABLE IF NOT EXISTS switch_v1(id INTEGER PRIMARY KEY CHECK(id=1),mode TEXT,generation INTEGER,changed TEXT);
    INSERT OR IGNORE INTO switch_v1 VALUES(1,'STOPPED',0,'never');
    CREATE TABLE IF NOT EXISTS challenges_v1(nonce TEXT PRIMARY KEY,user_id TEXT,chat_id TEXT,expires REAL,config_hash TEXT,generation INTEGER,used INTEGER DEFAULT 0);
    CREATE TABLE IF NOT EXISTS control_events_v1(seq INTEGER PRIMARY KEY,at TEXT,action TEXT,user_id TEXT,chat_id TEXT,detail TEXT);''')
    c.commit();return c

def event(c,action,user,chat,detail):
    c.execute('INSERT INTO control_events_v1(at,action,user_id,chat_id,detail) VALUES(?,?,?,?,?)',
        (timestamp(),action,str(user),str(chat),json.dumps(detail)))

def state(root=ROOT):
    c=connect(root)
    try:return dict(c.execute('SELECT mode,generation,changed FROM switch_v1 WHERE id=1').fetchone())
    finally:c.close()

def configuration(root=ROOT):
    raw=(Path(root)/'weex_ai_risk_config.json').read_bytes();c=json.loads(raw)
    if c['execution']['enabled'] is not False or c['execution']['mode']!='PRETRADE':raise ValueError('LEGACY_EXECUTION_MUST_REMAIN_PRETRADE')
    if (c['risk'].get('entryBudgetMode')!='COST_INCLUDING_ENTRY_FEE' or c['risk']['stopLoss']['enabled'] is not False
        or c['execution'].get('allowOrdersWithoutStop') is not True or c['strategySettings']['tpMode'] not in ('fixed','trailing')
        or c['strategySettings']['slMode']!='off'):raise ValueError('UNSUPPORTED_STRATEGY_SETTINGS')
    accounting=c['strategySettings'].get('tpAccountingMode','NET')
    if accounting not in ('NET','GROSS_BEFORE_COSTS') or (accounting=='GROSS_BEFORE_COSTS'
            and c['strategySettings']['tpMode']!='fixed'):
        raise ValueError('TP_ACCOUNTING_MODE_UNSUPPORTED')
    cost=Decimal(str(c['risk']['orderCostTargetUSDT']));tp=Decimal(str(c['strategySettings']['targetNetProfitUSDT']))
    cap=c['telegramSettings']['maxConcurrentPositions']['default']
    if not cost.is_finite() or cost<=0 or not tp.is_finite() or tp<=0 or type(cap) is not int or not 1<=cap<=10:
        raise ValueError('INVALID_BUDGET_OR_CAPACITY')
    return c,hashlib.sha256(raw).hexdigest()

def release_gate_errors(root=ROOT, now=None, max_age_seconds=600):
    """Require a fresh, complete independent release gate before any LIVE start or entry."""
    root=Path(root)
    try:
        gate=json.loads((root/'live_release_gate_latest.json').read_text(encoding='utf-8'))
        observed=gate.get('checkedAt') or gate.get('at')
        age=(time.time() if now is None else now)-datetime.fromisoformat(
            str(observed).replace('Z','+00:00')).timestamp()
        checks=gate.get('checks')
        audit_safe=(gate.get('ordersPlacedByAudit',gate.get('ordersSubmitted')) is False)
        if age<0 or age>max_age_seconds:return ['LIVE_RELEASE_GATE_STALE']
        if (gate.get('gate')!='GO' or not isinstance(checks,dict) or not checks
                or any(value is not True for value in checks.values())
                or gate.get('passed')!=gate.get('total') or not audit_safe):
            return ['LIVE_RELEASE_NO_GO']
        return []
    except (OSError,ValueError,KeyError,TypeError,AttributeError):
        return ['LIVE_RELEASE_GATE_UNAVAILABLE']

def build_errors(root=ROOT):
    root=Path(root);errors=[]
    try:
        release=json.loads((root/'live_release_manifest.json').read_text(encoding='utf-8'))
        if release.get('status')!='OFFLINE_VERIFIED_NO_REAL_ORDERS' or release.get('testsPassed') is not True:
            errors.append('COLLAUDO_NON_COMPLETATO')
        elif set(release['sha256'])!=set(CODE_FILES):
            errors.append('MANIFEST_INCOMPLETO')
        elif any(hashlib.sha256((root/f).read_bytes()).hexdigest()!=release['sha256'][f] for f in CODE_FILES):
            errors.append('CODICE_MODIFICATO_DOPO_COLLAUDO')
    except (OSError,ValueError,KeyError,TypeError):
        errors.append('COLLAUDO_NON_DISPONIBILE')
    # The historical release report is diagnostic, not a runtime prerequisite:
    # it is not refreshed by the worker and includes an unperformed live crash
    # experiment. Runtime readiness and per-entry guards validate current state.
    return sorted(set(errors))

def readiness(root=ROOT):
    # The independent release decision is mandatory for arming new entries.
    # TP recovery and read-only account reconciliation remain independent.
    errors=build_errors(root)+release_gate_errors(root)
    try:
        reconciliation=json.loads((Path(root)/'weex_reconcile_latest.json').read_text(encoding='utf-8'))
        age=time.time()-datetime.fromisoformat(reconciliation['checkedAt']).timestamp()
        if reconciliation.get('status') in ('RUNNING','WAIT_API','VERIFYING') and -30<=age<=1800:
            errors.append('RICONCILIAZIONE_IN_CORSO')
    except (OSError,ValueError,KeyError,TypeError):pass

    try:configuration(root)
    except Exception as exc:errors.append(str(exc) if isinstance(exc,ValueError) else 'CONFIG_NON_LEGGIBILE')
    try:
        h=json.loads((Path(root)/'weex_live_worker_latest.json').read_text(encoding='utf-8'))
        age=time.time()-datetime.fromisoformat(h['checkedAt']).timestamp()
        if not 0<=age<=420:errors.append('RUNNER_NON_RECENTE')
        if h.get('accountReadOK') is not True or h.get('recoveryClear') is not True:errors.append('CONTO_O_RECUPERO_DA_VERIFICARE')
        if h.get('host')!='https://api-contract.weex.com':errors.append('AMBIENTE_RUNNER_ERRATO')
    except (OSError,ValueError,KeyError,TypeError):errors.append('RUNNER_NON_VERIFICATO')
    return sorted(set(errors))

def request_start(user,chat,root=ROOT):
    errors=readiness(root)
    if errors:return {'accepted':False,'errors':errors}
    from weex_trading_modes import get_mode
    trading_mode=get_mode(root)['mode']
    if trading_mode=='alerts_only':return {'accepted':False,'errors':['MODALITA_SOLO_ALERT']}
    cfg,digest=configuration(root);nonce=secrets.token_urlsafe(18)
    c=connect(root)
    try:
        c.execute('BEGIN IMMEDIATE');s=c.execute('SELECT * FROM switch_v1 WHERE id=1').fetchone()
        if s['mode']=='RUNNING':c.rollback();return {'accepted':False,'errors':['GIA_AVVIATO']}
        c.execute('UPDATE challenges_v1 SET used=1 WHERE user_id=? AND chat_id=?',(str(user),str(chat)))
        c.execute('INSERT INTO challenges_v1 VALUES(?,?,?,?,?,?,0)',(nonce,str(user),str(chat),time.time()+120,digest,s['generation']))
        event(c,'START_PREVIEW',user,chat,{'generation':s['generation']});c.commit()
    finally:c.close()
    return {'accepted':True,'nonce':nonce,'cost':str(cfg['risk']['orderCostTargetUSDT']),
        'tp':str(cfg['strategySettings']['targetNetProfitUSDT']),'maxPositions':cfg['telegramSettings']['maxConcurrentPositions']['default'],
        'tpDescription':__import__('weex_trailing').description(cfg['strategySettings']),
        'minimumLeverage':str(cfg['risk'].get('minimumLeverage',100)),
        'tradingMode':trading_mode,'tradingModeLabel':{'automatic':'Automatico','automatic_manual':'Automatico + manuale','manual_only':'Solo manuale'}[trading_mode]}

def confirm_start(nonce,user,chat,root=ROOT):
    errors=readiness(root)
    if errors:return {'started':False,'errors':errors}
    from weex_trading_modes import get_mode
    if get_mode(root)['mode']=='alerts_only':return {'started':False,'errors':['MODALITA_SOLO_ALERT']}
    _,digest=configuration(root);c=connect(root)
    try:
        c.execute('BEGIN IMMEDIATE');s=c.execute('SELECT * FROM switch_v1 WHERE id=1').fetchone()
        n=c.execute('SELECT * FROM challenges_v1 WHERE nonce=?',(nonce,)).fetchone()
        if (not n or n['used'] or n['user_id']!=str(user) or n['chat_id']!=str(chat) or n['expires']<time.time()
            or n['config_hash']!=digest or n['generation']!=s['generation'] or s['mode']!='STOPPED'):
            c.rollback();return {'started':False,'errors':['CONFERMA_SCADUTA_USATA_O_IMPOSTAZIONI_CAMBIATE']}
        c.execute('UPDATE challenges_v1 SET used=1')
        c.execute("UPDATE switch_v1 SET mode='RUNNING',generation=generation+1,changed=? WHERE id=1",(timestamp(),))
        event(c,'USER_CONFIRMED_START',user,chat,{'configHash':digest});c.commit()
        return {'started':True}
    finally:c.close()

def stop(user,chat,root=ROOT):
    from weex_trading_modes import cancel_pending_manual
    c=connect(root)
    try:
        c.execute('BEGIN IMMEDIATE')
        c.execute("UPDATE switch_v1 SET mode='STOPPED',generation=generation+1,changed=? WHERE id=1",(timestamp(),))
        c.execute('UPDATE challenges_v1 SET used=1')
        event(c,'USER_STOP_NEW_ENTRIES',user,chat,{'existingTPsPreserved':True});c.commit()
        cancel_pending_manual(root,'LIVE_SWITCH_STOPPED')
        return {'stopped':True}
    finally:c.close()

@contextmanager
def dispatch_permission(root,generation,config_hash):
    """Serialize the final authorization and HTTP send against STOP acknowledgement."""
    c=connect(root)
    try:
        c.execute('BEGIN IMMEDIATE');s=c.execute('SELECT * FROM switch_v1 WHERE id=1').fetchone()
        if s['mode']!='RUNNING' or s['generation']!=generation:raise PermissionError('LIVE_STOPPED_OR_REARMED')
        if configuration(root)[1]!=config_hash:raise PermissionError('SETTINGS_CHANGED_BEFORE_DISPATCH')
        if build_errors(root):raise PermissionError('RELEASE_CHANGED')
        if release_gate_errors(root):raise PermissionError('LIVE_RELEASE_NOT_CERTIFIED')
        yield
        c.commit()
    except BaseException:c.rollback();raise
    finally:c.close()

def display(root=ROOT):
    from weex_trading_modes import get_mode
    s=state(root);trading_mode=get_mode(root)['mode']
    labels={'automatic':'AUTOMATICO','alerts_only':'SOLO ALERT','automatic_manual':'AUTOMATICO + MANUALE','manual_only':'SOLO MANUALE'}
    if s['mode']!='RUNNING':effective='INGRESSI LIVE FERMI'
    elif trading_mode=='alerts_only':effective='SOLO ALERT · NESSUN NUOVO INGRESSO'
    else:
        errors=readiness(root)
        effective='ARMATO MA BLOCCATO: '+', '.join(errors) if errors else 'INGRESSI LIVE ABILITATI'
    return f"MODALITÀ: {labels.get(trading_mode,trading_mode)} · {effective}"
