"""Two local quality auditors, called by the existing Windows watchdog.

Audits read bot evidence only. This coordinator writes its own reports/outbox,
never the strategy, live control, trading journal or exchange. No LLM/cloud.
"""
import hashlib,json,os,sqlite3,time
from contextlib import closing
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parent
DB='weex_quality_auditors.sqlite3'

def connect(root):
    c=sqlite3.connect(Path(root)/DB,timeout=2);c.row_factory=sqlite3.Row
    c.executescript('''CREATE TABLE IF NOT EXISTS findings_v1(
      key TEXT PRIMARY KEY,signature TEXT,notified TEXT,first REAL,last REAL,agent TEXT,body TEXT);
    CREATE TABLE IF NOT EXISTS outbox_v1(
      id INTEGER PRIMARY KEY AUTOINCREMENT,created REAL,text TEXT,status TEXT,message_id TEXT);
    CREATE TABLE IF NOT EXISTS meta_v1(key TEXT PRIMARY KEY,value REAL);''')
    return c

def signature(finding):
    # Evidence counts/timestamps can change every loop. A proposal is notified
    # again only when the actual classification or recommendation changes.
    basis={k:finding.get(k) for k in ('key','severity','code','recommendation')}
    return hashlib.sha256(json.dumps(basis,sort_keys=True).encode()).hexdigest()

def persist(root,reports,now):
    with closing(connect(root)) as c,c:
        c.execute('BEGIN IMMEDIATE')
        for agent,report in reports.items():
            for finding in report.get('findings',[]):
                if not isinstance(finding,dict) or not finding.get('key'):continue
                key=agent+':'+str(finding['key']);sig=signature(finding)
                c.execute('''INSERT INTO findings_v1 VALUES(?,?,NULL,?,?,?,?)
                  ON CONFLICT(key) DO UPDATE SET signature=excluded.signature,last=excluded.last,body=excluded.body''',
                  (key,sig,now,now,agent,json.dumps(finding,ensure_ascii=False)))
        # Only findings observed now are eligible, so old/stale pending findings
        # do not later create misleading current alerts.
        pending=[dict(r) for r in c.execute('SELECT * FROM findings_v1 WHERE last=? AND (notified IS NULL OR notified!=signature)',(now,))]
        if not pending:return 0
        last=c.execute("SELECT value FROM meta_v1 WHERE key='digest_at'").fetchone()
        urgent=[r for r in pending if json.loads(r['body']).get('severity') in ('ERROR','CRITICAL')]
        selected=urgent if last and now-last[0]<900 else pending
        if not selected:return 0
        selected=selected[:8]
        lines=['WEEX - AUDIT LOCALE','Analisi alert e risultati; nessuna modifica automatica.']
        for row in selected:
            f=json.loads(row['body']);label='Alert' if row['agent']=='alerts' else 'Chiusure'
            symbol=f.get('evidence',{}).get('symbol')
            if symbol:label+=' '+str(symbol)[:40]
            lines.append(f"\n{label} | {f.get('code',f['key'])}")
            lines.append(str(f.get('recommendation','Verificare il report locale.'))[:260])
        if len(pending)>len(selected):lines.append('\nAltri rilievi nei report locali; riepilogo successivo senza ripetizioni.')
        c.execute('INSERT INTO outbox_v1(created,text,status) VALUES(?,?,?)',(now,'\n'.join(lines),'PENDING'))
        for row in selected:c.execute('UPDATE findings_v1 SET notified=signature WHERE key=?',(row['key'],))
        c.execute("INSERT OR REPLACE INTO meta_v1 VALUES('digest_at',?)",(now,))
        return len(selected)

def save(path,value):
    tmp=path.with_suffix('.'+str(os.getpid())+'.tmp')
    tmp.write_text(json.dumps(value,indent=2,ensure_ascii=False),encoding='utf-8');os.replace(tmp,path)

def run(root=ROOT,now=None,auditors=None):
    root=Path(root);now=time.time() if now is None else now
    from weex_alert_archive import initialize
    initialize(root)
    if auditors is None:
        from weex_alert_quality import audit as alert_audit
        from weex_closed_quality import audit as closed_audit
        auditors={'alerts':alert_audit,'closed':closed_audit}
    reports={}
    for name,fn in auditors.items():
        try:result=fn(root,now=now)
        except Exception as exc:
            result={'status':'ERROR','findings':[{'key':'audit_unavailable','severity':'ERROR','code':'AUDIT_UNAVAILABLE',
                    'evidence':{'errorClass':type(exc).__name__},'recommendation':'Audit locale '+name+' non disponibile: controllare la lettura dei registri.'}]}
        normalized=[]
        for original in result.get('findings',[]):
            f=dict(original);f['key']=f.get('key') or f.get('stableKey')
            if not f['key']:continue
            f['severity']=str(f.get('severity','INFO')).upper()
            f['code']=f.get('code') or (str(f['key']).split(':')[1] if ':' in str(f['key']) else str(f['key'])).upper()
            normalized.append(f)
        result['findings']=normalized
        result.update(checkedAt=datetime.fromtimestamp(now,timezone.utc).isoformat(),execution='LOCAL_READ_ONLY',exchangeRequests=0,strategyModified=False)
        save(root/('weex_'+('alert' if name=='alerts' else 'closed')+'_quality_latest.json'),result);reports[name]=result
    count=persist(root,reports,now)
    summary={'checkedAt':datetime.fromtimestamp(now,timezone.utc).isoformat(),'pid':os.getpid(),
             'execution':'LOCAL_WINDOWS_WATCHDOG','cadenceSeconds':120,
             'agents':{n:{'status':v.get('status'),'findingCount':len(v.get('findings',[]))} for n,v in reports.items()},
             'queuedFindings':count,'exchangeRequests':0,'strategyModified':False}
    save(root/'weex_quality_auditors_latest.json',summary)
    return summary

def drain(root,sender):
    path=Path(root)/DB
    if not path.exists():return None
    with closing(connect(root)) as c,c:
        c.execute('BEGIN IMMEDIATE')
        row=c.execute("SELECT * FROM outbox_v1 WHERE status='PENDING' ORDER BY id LIMIT 1").fetchone()
        if row is None:return None
        c.execute("UPDATE outbox_v1 SET status='SENDING' WHERE id=?",(row['id'],))
    try:mid=sender(row['text'])
    except Exception:
        with closing(connect(root)) as c,c:c.execute("UPDATE outbox_v1 SET status='DELIVERY_UNCERTAIN' WHERE id=?",(row['id'],))
        return {'status':'DELIVERY_UNCERTAIN','retry':False}
    with closing(connect(root)) as c,c:c.execute("UPDATE outbox_v1 SET status='SENT',message_id=? WHERE id=?",(str(mid),row['id']))
    return {'status':'SENT','messageId':mid}

if __name__=='__main__':print(json.dumps(run()))
