"""Read local reports, reserve bounded recovery, verify new evidence.

Returns only allowlisted local task/process starts; never orders, live switch,
source edits, journal resets, task installation or killing running processes.
"""
import json,time,sqlite3
from datetime import datetime,timezone
from pathlib import Path
from weex_incidents import Store,budget_ready_at

def load(root,name):
    try:return json.loads((Path(root)/name).read_text(encoding='utf-8-sig'))
    except (OSError,ValueError):return {}

def stamp(value):
    try:return datetime.fromisoformat(value.replace('Z','+00:00')).timestamp()
    except (ValueError,TypeError,AttributeError):return 0

def supervise(root,snapshot,*,clock=time.time):
    root=Path(root);now=clock();store=Store(root,clock);actions=[];issues=[]
    def observe(key,code,*,manual=False,next_at=None,evidence=None):
        issues.append(key)
        return store.observe(key,code,'ATTENTION' if manual else 'WAITING',next_at,evidence or now)
    def attempt(key,action):
        r=store.get(key)
        if r and r['state']=='VERIFYING' and now<r['next_at']:return
        if store.claim(key,delay=600):
            actions.append(action)
            store.observe(key,store.get(key)['code'],'VERIFYING',next_at=now+600,evidence_at=now)
    inventory_at=stamp(snapshot.get('capturedAt'))
    fresh_inventory=0<=now-inventory_at<=30
    if not fresh_inventory:observe('inventory','INVENTORY_UNAVAILABLE',manual=True)
    else:store.resolve('inventory',inventory_at,healthy=True)
    for key,field,action in [('telegram','telegramPids',{'kind':'START_TELEGRAM_PROCESS'}),
                             ('notifications','monitorPids',{'kind':'START_MONITOR_PROCESS'})]:
        ids=snapshot.get(field)
        if not fresh_inventory or not isinstance(ids,list):continue
        if len(ids)>1:observe(key,'DUPLICATE_PROCESS',manual=True)
        elif not ids:
            old=store.get(key)
            if not old or old['state']=='RESOLVED':observe(key,'PROCESS_MISSING')
            else:issues.append(key)
            attempt(key,action)
        else:
            # PID existence alone is insufficient: require a new app heartbeat.
            heartbeat=load(root,'weex_service_health_'+key+'.json')
            at=stamp(heartbeat.get('checkedAt'))
            healthy=(heartbeat.get('pid')==ids[0] and heartbeat.get('status')=='OK' and 0<=now-at<=90)
            if healthy:store.resolve(key,at,healthy=True,ttl=90)
            elif not store.get(key) or store.get(key)['state']=='RESOLVED' or now>=store.get(key)['next_at']:
                observe(key,'STALE_REPORT',manual=True)
    # Scan recovery is GET-only and remains subordinate to shared API allowance.
    market=load(root,'market_agents_latest.json');at=stamp(market.get('asOf'))
    healthy=0<=now-at<=720 and market.get('analysisComplete') is True
    if healthy:
        store.resolve('scanner',at,healthy=True,ttl=720)
        store.resolve('scanner:budget',at,healthy=True,ttl=720)
    else:
        old=store.get('scanner')
        if not old or old['state']=='RESOLVED':observe('scanner','STALE_REPORT',evidence=now)
        else:issues.append('scanner')
        try:ready=budget_ready_at(root,weight=5,headroom=0,now=now)
        except (OSError,ValueError,sqlite3.Error):
            # Database/inventory uncertainty cannot authorize a restart.
            ready=None
        task='WEEX_AI_Market_Diagnostics';state=snapshot.get('tasks',{}).get(task)
        if ready is None:observe('scanner:budget','UNKNOWN_ERROR',manual=True)
        elif ready>now:observe('scanner:budget','API_BUDGET',next_at=ready)
        elif fresh_inventory and state=='Ready':
            store.resolve('scanner:budget',now,healthy=True)
            attempt('scanner',{'kind':'START_EXISTING_TASK','task':task})
        elif fresh_inventory and state=='Running' and now-store.get('scanner')['first']>=300:
            observe('scanner','STALE_REPORT',manual=True)
        elif fresh_inventory and state not in ('Ready','Running'):observe('scanner','UNKNOWN_ERROR',manual=True)
    # Actual live recovery is an independent responsibility. Do not restart it,
    # edit its journal, adopt a foreign TP, or claim success from a fresh timestamp.
    worker=load(root,'weex_live_worker_latest.json');at=stamp(worker.get('checkedAt'))
    if 0<=now-at<=420:
        if worker.get('recoveryClear') is True and worker.get('accountReadOK') is True:
            store.resolve('orders',at,healthy=True,ttl=420)
        elif worker.get('recoveryClear') is False:observe('orders','ORDER_REVIEW',manual=True,evidence=at)
    else:observe('orders:observation','STALE_REPORT',manual=True)
    if 0<=now-at<=420:store.resolve('orders:observation',at,healthy=True,ttl=420)
    with store.db() as c:incidents=[dict(r) for r in c.execute("SELECT * FROM incidents WHERE state!='RESOLVED'")]
    result={'checkedAt':datetime.fromtimestamp(now,timezone.utc).isoformat(),'mode':'BOUNDED_INCIDENT_SUPERVISION',
            'status':'ATTENTION' if any(r['state']=='ATTENTION' for r in incidents) else 'RECOVERING' if incidents else 'OK',
            'issues':issues,'actions':actions,'incidents':incidents,'ordersSubmitted':False,'exchangeWrites':0}
    target=root/'weex_incident_supervisor_latest.json';tmp=target.with_suffix('.tmp')
    tmp.write_text(json.dumps(result,indent=2),encoding='utf-8');tmp.replace(target)
    return result
