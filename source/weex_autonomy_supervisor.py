"""Finite recovery planning for existing PRETRADE workers; no exchange client."""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

TASKS = {
    'market': 'WEEX_AI_Market_Diagnostics',
    'positions': 'WEEX_AI_Integrated_Position_Audit',
    'universe': 'WEEX_AI_Universe_Refresh',
}
SOURCES = {
    'market': [('market_agents_latest.json', 'asOf', 720),
               ('weex_simple_bot_latest.json', 'checkedAt', 720),
               ('weex_execution_cycle_latest.json', 'checkedAt', 420),
               ('weex_agent_orchestrator_latest.json', 'checkedAt', 720)],
    'positions': [('position_manager_integrated_latest.json', 'asOf', 600)],
    'universe': [('universe_latest.json', 'scannedAt', 93600)],
}

def age(stamp, now):
    try:
        value = (now - datetime.fromisoformat(stamp.replace('Z', '+00:00'))).total_seconds()
        return value if value >= 0 else None
    except (ValueError, TypeError, AttributeError):
        return None

def plan(snapshot, reports, previous=None, now=None):
    now = now or datetime.now(timezone.utc)
    previous = previous or {}
    cfg = reports.get('weex_ai_risk_config.json', {}).get('execution', {})
    result = {'checkedAt': now.isoformat(), 'mode': 'PRETRADE_SUPERVISION',
              'status': 'OK', 'issues': [], 'actions': [],
              'ordersSubmitted': False, 'exchangeWrites': 0,
              'lastAttempts': dict(previous.get('lastAttempts', {}))}
    if cfg.get('enabled') is not False or cfg.get('mode') != 'PRETRADE':
        result.update(status='BLOCKED_CONFIG', issues=['PRETRADE_CONFIG_REQUIRED'])
        return result
    def request(key, action):
        elapsed = age(result['lastAttempts'].get(key), now)
        # Future/invalid persisted timestamps fail closed instead of bypassing cooldown.
        if key in result['lastAttempts'] and (elapsed is None or elapsed < 600):
            result['issues'].append(key + ':RECOVERY_COOLDOWN')
            return
        result['actions'].append(action)
        # Persist reservation before the caller performs any process/task action.
        result['lastAttempts'][key] = now.isoformat()
    for group, sources in SOURCES.items():
        problems = []
        for name, key, ttl in sources:
            report = reports.get(name, {})
            elapsed = age(report.get(key), now)
            if elapsed is None or elapsed > ttl:
                problems.append(name + ':STALE_OR_MISSING')
        if group == 'market':
            market = reports.get('market_agents_latest.json', {})
            pretrade = reports.get('weex_simple_bot_latest.json', {})
            execution = reports.get('weex_execution_cycle_latest.json', {})
            orchestrator = reports.get('weex_agent_orchestrator_latest.json', {})
            if execution.get('status') != 'OK': problems.append('EXECUTION_NOT_OK')
            if orchestrator.get('cycleStatus') != 'OK': problems.append('ORCHESTRATOR_NOT_OK')
            if (pretrade.get('sourceMarketAt') != market.get('asOf') or
                    execution.get('scanAt') != pretrade.get('checkedAt')):
                problems.append('REPORT_BATCH_MISMATCH')
            if execution.get('exchangeWrites', 0) != 0 or pretrade.get('ordersSubmitted', False) is not False:
                result.update(status='BLOCKED_CONFIG', issues=['UNEXPECTED_WRITE_STATE'], actions=[])
                return result
        if group == 'positions' and reports.get(sources[0][0], {}).get('completeWithinBounds') is not True:
            problems.append('POSITIONS_INCOMPLETE')
        deferred=reports.get('weex_simple_bot_latest.json',{})
        deferred_age=age(deferred.get('checkedAt'),now)
        if (group=='market' and deferred.get('diagnosticPolicy')=='CHECK_ONCE_IN_LIVE_WORKER'
                and deferred.get('status')=='WAIT_API_BUDGET' and deferred_age is not None and deferred_age<720
                and not reports.get('weex_execution_cycle_latest.json',{}).get('reconciliationNeededCount')):
            result['issues'].append('MARKET_WAIT_API_BUDGET')
            continue
        if problems:
            result['issues'].extend(problems)
            task = TASKS[group]
            state = snapshot.get('tasks', {}).get(task)
            if state == 'Ready': request(group, {'kind': 'START_EXISTING_TASK', 'task': task})
            elif state != 'Running': result['issues'].append(task + ':UNAVAILABLE')
    process_ids = snapshot.get('telegramPids')
    if not isinstance(process_ids, list):
        result['issues'].append('TELEGRAM_PROCESS_INVENTORY_UNAVAILABLE')
    elif not process_ids:
        result['issues'].append('TELEGRAM_PROCESS_MISSING')
        request('telegram', {'kind': 'START_TELEGRAM_PROCESS'})
    elif len(process_ids) > 1:
        result['issues'].append('TELEGRAM_DUPLICATE_PROCESSES_REVIEW_REQUIRED')
    if result['issues']: result['status'] = 'RECOVERY_REQUESTED' if result['actions'] else 'DEGRADED'
    if result['issues']==['MARKET_WAIT_API_BUDGET'] and not result['actions']:result['status']='WAIT_API_BUDGET'
    return result

def load(path):
    try:
        value = json.loads(path.read_text(encoding='utf-8-sig'))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError): return {}

def run(root, snapshot):
    root = Path(root)
    names = {name for entries in SOURCES.values() for name, _, _ in entries}
    names.add('weex_ai_risk_config.json')
    target = root / 'weex_autonomy_supervisor_latest.json'
    result = plan(snapshot, {name: load(root / name) for name in names}, load(target))
    temp = target.with_suffix('.tmp')
    temp.write_text(json.dumps(result, indent=2), encoding='utf-8')
    temp.replace(target)
    return result

if __name__ == '__main__':
    from weex_incident_supervisor import supervise
    from weex_execution_cycle import exclusive
    root=Path(__file__).resolve().parent
    with exclusive(root/'weex_incident_supervisor.lock'):
        print(json.dumps(supervise(root,load(Path(sys.argv[1])))))
