"""Durable incidents and notification outbox. No exchange or process executor."""
import json,sqlite3,time,math
from contextlib import contextmanager,closing
from pathlib import Path

STATES={'WAITING','RECOVERING','VERIFYING','ATTENTION','RESOLVED'}
LABELS={'API_BUDGET':'attesa budget API','CONNECTION':'connessione temporaneamente assente',
        'PROCESS_MISSING':'processo assente','STALE_REPORT':'dati non aggiornati',
        'ORDER_REVIEW':'ordine o TP da riconciliare','UNKNOWN_ERROR':'errore da verificare',
        'INVENTORY_UNAVAILABLE':'inventario processi non disponibile','DUPLICATE_PROCESS':'processi duplicati',
        'RETRIES_EXHAUSTED':'tentativi di recupero esauriti','CLOCK_INVALID':'orologio non valido'}
TITLES={'WAITING':'ATTESA','RECOVERING':'RECUPERO IN CORSO','VERIFYING':'VERIFICA IN CORSO',
        'ATTENTION':'INTERVENTO NECESSARIO','RESOLVED':'RISOLTO E VERIFICATO'}

class Store:
    def __init__(self,root,clock=time.time):
        self.path=Path(root)/'weex_incidents.sqlite3';self.clock=clock
        with self.db() as c:c.executescript('''
        CREATE TABLE IF NOT EXISTS incidents(key TEXT PRIMARY KEY,generation INTEGER,state TEXT,code TEXT,
          first REAL,last REAL,next_at REAL,attempts INTEGER,evidence_at REAL);
        CREATE TABLE IF NOT EXISTS incident_events(seq INTEGER PRIMARY KEY,key TEXT,generation INTEGER,
          at REAL,state TEXT,code TEXT,attempts INTEGER);
        CREATE TABLE IF NOT EXISTS incident_outbox(seq INTEGER PRIMARY KEY,text TEXT,status TEXT,message_id TEXT);
        ''')
    @contextmanager
    def db(self):
        c=sqlite3.connect(self.path,timeout=10);c.row_factory=sqlite3.Row
        c.execute('PRAGMA synchronous=FULL')
        try:
            with c:yield c
        finally:c.close()
    def get(self,key):
        with self.db() as c:r=c.execute('SELECT * FROM incidents WHERE key=?',(key,)).fetchone()
        return dict(r) if r else None
    def event(self,c,row):
        cur=c.execute('INSERT INTO incident_events(key,generation,at,state,code,attempts) VALUES(?,?,?,?,?,?)',
                      (row['key'],row['generation'],self.clock(),row['state'],row['code'],row['attempts']))
        # No exception text, URLs, credentials or arbitrary report fields in alerts.
        scope={'telegram':'comandi Telegram','notifications':'notifiche','scanner':'scansione',
               'scanner:budget':'budget scansione','public:budget':'budget letture pubbliche',
               'public:connection':'letture pubbliche','orders':'ordini e TP','orders:observation':'osservazione del runner',
               'inventory':'inventario servizi'}.get(row['key'],'servizio')
        text=f"WEEX - {TITLES[row['state']]}\n{scope}: {LABELS[row['code']]}\nTentativi: {row['attempts']}/3"
        if row['state']=='RESOLVED':text+='\nEsito verificato con una nuova osservazione.'
        elif row['state']=='ATTENTION':text+='\nNessuna modifica automatica a ordini o configurazione.'
        c.execute('INSERT INTO incident_outbox VALUES(?,?,?,NULL)',(cur.lastrowid,text,'PENDING'))
    def observe(self,key,code,state='WAITING',next_at=None,evidence_at=None):
        if code not in LABELS or state not in STATES-{'RESOLVED'}:raise ValueError('INVALID_INCIDENT')
        now=self.clock();next_at=now if next_at is None else next_at
        if not all(math.isfinite(x) for x in (now,next_at)):raise ValueError('INVALID_CLOCK')
        with self.db() as c:
            c.execute('BEGIN IMMEDIATE');old=c.execute('SELECT * FROM incidents WHERE key=?',(key,)).fetchone()
            if old and now<old['last']:raise ValueError('CLOCK_MOVED_BACKWARD')
            # An old observation cannot reopen a resolved incident.
            if old and old['state']=='RESOLVED' and (evidence_at is None or evidence_at<=old['evidence_at']):return dict(old)
            new=not old or old['state']=='RESOLVED'
            row=dict(old) if old else {}
            row.update(key=key,generation=(old['generation']+1 if old else 1) if new else old['generation'],
                       state=state,code=code,first=now if new else old['first'],last=now,next_at=next_at,
                       attempts=0 if new else old['attempts'],evidence_at=evidence_at or (old['evidence_at'] if old else 0))
            # Preserve exhausted/ambiguous recovery until fresh healthy evidence arrives.
            if old and not new and old['state']=='ATTENTION':row.update(state=old['state'],code=old['code'])
            c.execute('INSERT OR REPLACE INTO incidents VALUES(:key,:generation,:state,:code,:first,:last,:next_at,:attempts,:evidence_at)',row)
            if new or (row['state'],row['code'])!=(old['state'],old['code']):self.event(c,row)
            return row
    def claim(self,key,delay=60):
        """Atomic reservation BEFORE an allowlisted retry or process start."""
        with self.db() as c:
            c.execute('BEGIN IMMEDIATE');r=c.execute('SELECT * FROM incidents WHERE key=?',(key,)).fetchone()
            if not r:return None
            r=dict(r);now=self.clock()
            if r['state'] in ('RESOLVED','ATTENTION') or now<max(r['last'],r['next_at']):return None
            if r['attempts']>=3:
                r.update(state='ATTENTION',code='RETRIES_EXHAUSTED',last=now)
                c.execute('UPDATE incidents SET state=:state,code=:code,last=:last WHERE key=:key',r);self.event(c,r);return None
            r.update(state='RECOVERING',attempts=r['attempts']+1,last=now,next_at=now+delay)
            c.execute('UPDATE incidents SET state=:state,attempts=:attempts,last=:last,next_at=:next_at WHERE key=:key',r)
            self.event(c,r);return r
    def resolve(self,key,evidence_at,*,healthy,ttl=60):
        now=self.clock()
        if healthy is not True or not isinstance(evidence_at,(int,float)) or not math.isfinite(evidence_at) or not 0<=now-evidence_at<=ttl:return False
        with self.db() as c:
            c.execute('BEGIN IMMEDIATE');old=c.execute('SELECT * FROM incidents WHERE key=?',(key,)).fetchone()
            if not old or old['state']=='RESOLVED' or evidence_at<=max(old['first'],old['evidence_at']) or now<old['last']:return False
            r=dict(old);r.update(state='RESOLVED',last=now,evidence_at=evidence_at)
            c.execute('UPDATE incidents SET state=:state,last=:last,evidence_at=:evidence_at WHERE key=:key',r);self.event(c,r);return True
    def drain(self,sender,limit=4):
        # At-most-once attempts. A crash after reservation requires review, not replay.
        with self.db() as c:
            c.execute('BEGIN IMMEDIATE')
            rows=c.execute("SELECT seq,text FROM incident_outbox WHERE status='PENDING' ORDER BY seq LIMIT ?",(limit,)).fetchall()
            for r in rows:c.execute("UPDATE incident_outbox SET status='SENDING' WHERE seq=?",(r['seq'],))
        for r in rows:
            try:mid=sender(r['text']);status='SENT'
            except Exception:mid=None;status='DELIVERY_UNCERTAIN'
            with self.db() as c:c.execute('UPDATE incident_outbox SET status=?,message_id=? WHERE seq=?',(status,str(mid) if mid else None,r['seq']))
        return len(rows)

def budget_ready_at(root,weight=5,now=None,headroom=0):
    """Estimate readiness from the cached WEEX-declared windows."""
    from weex_api_budget import Budget
    now=time.time() if now is None else now
    b=Budget(root)
    b.ensure_limits()
    status=b.used()
    return max(now,status.get('pauseUntil',0),b.ready_at(weight,headroom,now))
