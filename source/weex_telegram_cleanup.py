"""Local cleanup of proven duplicate fills and short resolved budget chatter.

Only known acknowledged outbound message IDs. Never infer IDs, delete distinct
fills, command replies, scan start/results, or unresolved/critical incidents.
Original evidence stays in its source and a deletion journal. No exchange calls.
"""
import hashlib,json,logging,sqlite3,time,urllib.request
from collections import defaultdict
from contextlib import closing
from pathlib import Path

DB='weex_telegram_cleanup.sqlite3'
AGE=47*3600  # Headroom below Telegram's 48h limit.

def read(root,name,sql,args=()):
    path=Path(root)/name
    if not path.exists():return []
    with closing(sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True,timeout=2)) as c:
        c.row_factory=sqlite3.Row
        return [dict(r) for r in c.execute(sql,args)]

def mid(value):
    if isinstance(value,bool):return None
    try:n=int(value)
    except (TypeError,ValueError):return None
    return n if n>0 and str(n)==str(value) else None

def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()

def plan(root,now=None):
    now=time.time() if now is None else now
    candidates=[];groups=defaultdict(dict)
    rows=read(root,'weex_alert_archive.sqlite3',
        "SELECT * FROM outbound_events_v1 WHERE stage='SENT' AND at>=? AND at<=? ORDER BY at,seq",(now-AGE,now-60))
    for row in rows:
        if row['source']!='monitor.fill':continue
        content=json.loads(row['content']);outcome=json.loads(row['outcome'])
        f=content.get('fill');message=mid(outcome.get('messageId'))
        if not message or not isinstance(f,dict):continue
        if not all(f.get(k) is not None for k in ('symbol','positionSide','side','orderId','id')):continue
        # Content equality prevents removing a corrected version or a different
        # rendering with additional information, even for the same fill.
        key=(row['method'],digest(content))
        groups[key].setdefault(message,{'messageId':message,'at':row['at'],'content':content,'sourceSeq':row['seq']})
    for values in groups.values():
        messages=sorted(values.values(),key=lambda r:(r['at'],r['messageId']))
        for extra in messages[1:]:
            candidates.append(dict(extra,reason='EXACT_DUPLICATE_FILL',keepMessageId=messages[0]['messageId']))

    incidents=read(root,'weex_incidents.sqlite3',
        '''SELECT e.seq,e.key,e.generation,e.at,e.state,e.code,o.status,o.message_id,o.text
        FROM incident_events e JOIN incident_outbox o ON o.seq=e.seq
        WHERE e.at>=? AND e.at<=? ORDER BY e.at,e.seq''',(now-AGE,now))
    episodes=defaultdict(list)
    for row in incidents:episodes[(row['key'],row['generation'])].append(row)
    for episode in episodes.values():
        if any(r['code']!='API_BUDGET' or r['state'] not in ('WAITING','RECOVERING','VERIFYING','RESOLVED') for r in episode):continue
        waits=[r for r in episode if r['state']=='WAITING']
        ends=[r for r in episode if r['state']=='RESOLVED' and r['status']=='SENT' and mid(r['message_id'])]
        if not waits or len(ends)!=1:continue
        end=ends[0]
        if not 0<=end['at']-waits[0]['at']<=60 or now-end['at']<60:continue
        for row in episode:
            message=mid(row['message_id'])
            if row['state']=='RESOLVED' or row['at']>end['at'] or row['status']!='SENT' or not message:continue
            keep=mid(end['message_id'])
            if message==keep:continue
            candidates.append({'messageId':message,'at':row['at'],'reason':'TRANSIENT_BUDGET_RESOLVED',
                'keepMessageId':keep,'sourceSeq':row['seq'],'content':{'text':row['text']},
                'incidentKey':row['key'],'generation':row['generation']})
    # Never remove a retained anchor, even if source evidence is inconsistent.
    anchors={r['keepMessageId'] for r in candidates}
    unique={}
    for row in candidates:
        if row['messageId'] not in anchors:unique.setdefault(row['messageId'],row)
    return sorted(unique.values(),key=lambda r:r['messageId'])

def connect(root):
    c=sqlite3.connect(Path(root)/DB,timeout=2)
    c.executescript('''CREATE TABLE IF NOT EXISTS cleanup_v1(
      message_id INTEGER PRIMARY KEY,status TEXT,at REAL,evidence TEXT,error_class TEXT);
      CREATE TABLE IF NOT EXISTS cleanup_meta_v1(key TEXT PRIMARY KEY,value TEXT);''')
    return c

def delete_message(cfg,message_id):
    # Credentials are read only by the existing monitor and never logged here.
    request=urllib.request.Request('https://api.telegram.org/bot'+cfg['telegram_bot_token']+'/deleteMessage',
        json.dumps({'chat_id':cfg['telegram_chat_id'],'message_id':message_id}).encode(),{'Content-Type':'application/json'})
    with urllib.request.urlopen(request,timeout=8) as response:result=json.load(response)
    if result.get('ok') is not True or result.get('result') is not True:raise RuntimeError('DELETE_NOT_CONFIRMED')
    return True

def tick(root,cfg,*,now=None,deleter=None):
    """At most five known deletions per minute, independently of trading logic."""
    root=Path(root);now=time.time() if now is None else now
    scope=digest([cfg['telegram_bot_token'],str(cfg['telegram_chat_id'])])
    with closing(connect(root)) as c,c:
        c.execute('BEGIN IMMEDIATE')
        meta=dict(c.execute('SELECT key,value FROM cleanup_meta_v1'))
        if meta.get('scope',scope)!=scope:return {'status':'BLOCKED_DESTINATION_CHANGED'}
        if now-float(meta.get('last',0))<60:return {'status':'WAIT'}
        c.execute("INSERT OR IGNORE INTO cleanup_meta_v1 VALUES('scope',?)",(scope,))
        c.execute("INSERT OR REPLACE INTO cleanup_meta_v1 VALUES('last',?)",(str(now),))
    proposed=plan(root,now)
    # A missing/uncertain retained message must not become the sole survivor.
    with closing(connect(root)) as c:
        prior=dict(c.execute('SELECT message_id,status FROM cleanup_v1'))
    eligible=[r for r in proposed if r['messageId'] not in prior and r['keepMessageId'] not in prior][:5]
    results=[]
    for row in eligible:
        # Preserve complete evidence and reserve before the external action.
        with closing(connect(root)) as c,c:
            claimed=c.execute('INSERT OR IGNORE INTO cleanup_v1 VALUES(?,?,?,?,NULL)',
                (row['messageId'],'DELETING',now,json.dumps(row,ensure_ascii=False))).rowcount
        if not claimed:continue
        try:
            if (deleter or delete_message)(cfg,row['messageId']) is not True:raise RuntimeError('DELETE_NOT_CONFIRMED')
            status='DELETED';error=None
        except Exception as exc:
            # No blind retries. A timeout could have completed on Telegram.
            status='DELETE_UNCERTAIN';error=type(exc).__name__
            logging.warning('Telegram cleanup not confirmed (%s)',error)
        with closing(connect(root)) as c,c:
            c.execute('UPDATE cleanup_v1 SET status=?,error_class=? WHERE message_id=?',(status,error,row['messageId']))
        results.append({'messageId':row['messageId'],'status':status,'reason':row['reason']})
    return {'status':'CHECKED','candidates':len(proposed),'actions':results}
