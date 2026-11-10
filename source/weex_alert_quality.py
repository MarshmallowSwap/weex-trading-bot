"""Deterministic local notification audit. Read-only; no network or execution."""
import json, math, sqlite3, time
from collections import Counter, defaultdict
from contextlib import closing
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

WINDOW=86400

def audit(root,now=None):
    root=Path(root).resolve();now=time.time() if now is None else float(now)
    if not math.isfinite(now):raise ValueError('INVALID_CLOCK')
    findings=[];errors=[];start=now-WINDOW
    def finding(key,severity,evidence,recommendation):
        findings.append({'stableKey':key,'severity':severity,'evidence':evidence,'recommendation':recommendation})
    def read(name,query,params=(),optional=False):
        path=root/name
        if optional and not path.exists():return []
        try:
            with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True,timeout=2)) as db:
                db.row_factory=sqlite3.Row
                return [dict(r) for r in db.execute(query,params)]
        except (sqlite3.Error,OSError) as exc:
            errors.append({'source':name,'errorClass':type(exc).__name__});return []
    def decode(text):
        try:r=json.loads(text);return r if isinstance(r,dict) else {}
        except (TypeError,ValueError):return {}
    archive=read('weex_alert_archive.sqlite3','SELECT * FROM outbound_events_v1 WHERE at>=? AND at<=? ORDER BY seq',(start,now))
    attempts=defaultdict(list)
    for r in archive:attempts[r['attempt_id']].append(r)
    sent=[];uncertain=[];pending=[]
    for aid,items in attempts.items():
        # A SENT acknowledgement takes precedence over intent/uncertain records.
        delivered=[r for r in items if r['stage']=='SENT']
        row=max(delivered or items,key=lambda x:x['seq']);row=dict(row)
        row['content']=decode(row['content']);row['outcome']=decode(row['outcome'])
        if delivered:sent.append(row)
        elif any(r['stage']=='DELIVERY_UNCERTAIN' for r in items):uncertain.append(row)
        else:pending.append(row)
    # Callback acknowledgements and edit calls are not new messages.
    messages=[r for r in sent if r['method'] in ('sendMessage','sendPhoto','sendDocument','sendVideo','sendAnimation','sendAudio')]
    unique={}
    for r in messages:
        mid=r['outcome'].get('messageId')
        identity=('message',str(mid)) if mid is not None else ('attempt',r['attempt_id'])
        unique.setdefault(identity,r)
    all_messages=sorted(unique.values(),key=lambda x:(x['at'],x['seq']))
    def audit_generated(row):
        return any(str(row['content'].get(k) or '').strip().startswith('WEEX - AUDIT LOCALE') for k in ('text','caption'))
    # The auditor's own digests must not create new alert-quality findings.
    messages=[r for r in all_messages if not audit_generated(r)]
    uncertain=[r for r in uncertain if not audit_generated(r)]
    pending=[r for r in pending if not audit_generated(r)]
    if uncertain:
        finding('alerts:delivery_uncertain','warning',{'attemptCount':len(uncertain),'seqs':[r['seq'] for r in uncertain][-30:],
                 'meaning':'Historical uncertain delivery attempts in window; not counted as delivered.'},
                 'Conservare esito incerto e verificare le ricevute; non ritentare alla cieca.')
    if pending:
        aged=[r for r in pending if now-r['at']>120]
        if aged:finding('alerts:unsettled_sending','warning',{'attemptCount':len(aged),'seqs':[r['seq'] for r in aged][-30:]},
                         'Verificare tentativi SENDING senza esito da oltre 120 secondi; non reinviare automaticamente.')
    orders=defaultdict(list);fill_attempts=defaultdict(list)
    for r in messages:
        f=r['content'].get('fill')
        if not isinstance(f,dict) or not all(f.get(k) is not None for k in ('orderId','id','symbol','side','positionSide')):continue
        key=(str(f['symbol']),str(f['positionSide']),str(f['side']),str(f['orderId']))
        orders[key].append((r,f));fill_attempts[(key,str(f['id']))].append(r)
    for key,pairs in orders.items():
        fillmap={str(f['id']):f for _,f in pairs}
        if len(fillmap)<2:continue
        evidence={'symbol':key[0],'positionSide':key[1],'side':key[2],'orderId':key[3],
                  'uniqueFillCount':len(fillmap),'acknowledgedMessageCount':len(pairs),
                  'seqs':[r['seq'] for r,f in pairs],'completeOrderProven':False,'historical':True}
        try:
            qty=sum(Decimal(str(f['qty'])) for f in fillmap.values());value=sum(Decimal(str(f['quoteQty'])) for f in fillmap.values())
            if qty.is_finite() and qty>0 and value.is_finite():evidence.update(quantity=str(qty),weightedPrice=str(value/qty))
        except (KeyError,InvalidOperation,ZeroDivisionError):pass
        finding('alerts:multifill:'+':'.join(key),'info',evidence,
                'Aggregare per ordine, sommare fill unici e usare prezzo medio ponderato. Separare chiusure parziali e ordini successivi; confermare completezza prima del riepilogo finale.')
    for (key,fid),rs in fill_attempts.items():
        if len(rs)>1:finding('alerts:repeated_fill:'+':'.join(key)+':'+fid,'warning',
            {'fillId':fid,'orderId':key[3],'acknowledgedMessageCount':len(rs),'seqs':[r['seq'] for r in rs],'historical':True},
            'Verificare deduplicazione persistente: lo stesso fill compare in più invii confermati.')
    # Sliding window; report maximum, rather than one finding for each overlap.
    left=0;best=[]
    for right,row in enumerate(messages):
        while row['at']-messages[left]['at']>60:left+=1
        if right-left+1>len(best):best=messages[left:right+1]
    if len(best)>5:
        finding('alerts:burst_60s','warning',{'count':len(best),'startAt':best[0]['at'],'endAt':best[-1]['at'],
                'seqs':[r['seq'] for r in best][:50],'historical':True},
                'Raggruppare notifiche informative per ciclo; lasciare immediati TP mancanti, ordini incerti e altri errori critici.')
    # Legacy stores provide context only: never added to acknowledgedMessageCount.
    legacy={}
    legacy['fills']=read('events.sqlite3','SELECT status,COUNT(*) AS count FROM events GROUP BY status',optional=True)
    legacy['scan']=read('events.sqlite3','SELECT kind,status,COUNT(*) AS count FROM scan_notifications_v1 WHERE created>=? AND created<=? GROUP BY kind,status',(start,now),optional=True)
    legacy['incidentOutbox']=read('weex_incidents.sqlite3','SELECT o.status,COUNT(*) AS count FROM incident_outbox o JOIN incident_events e ON e.seq=o.seq WHERE e.at>=? AND e.at<=? GROUP BY o.status',(start,now),optional=True)
    incident_events=read('weex_incidents.sqlite3','SELECT seq,key,generation,at,state,code FROM incident_events WHERE at>=? AND at<=? ORDER BY at,seq',(start,now),optional=True)
    budget=defaultdict(list)
    for r in incident_events:
        if r['code']=='API_BUDGET':budget[(r['key'],r['generation'])].append(r)
    rapid=[]
    for key,items in budget.items():
        waits=[r for r in items if r['state']=='WAITING'];resolves=[r for r in items if r['state']=='RESOLVED']
        if waits and resolves:
            wait=waits[0];resolved=next((r for r in resolves if r['at']>=wait['at']),None)
            if resolved and resolved['at']-wait['at']<=60:rapid.append({'key':key[0],'generation':key[1],'durationSeconds':resolved['at']-wait['at'],'seqs':[wait['seq'],resolved['seq']]})
    if rapid:finding('alerts:budget_flapping','info',{'rapidResolvedEpisodes':len(rapid),'episodes':rapid[-30:],
                            'source':'legacy incident_events; not extra delivered-message counts','historical':True},
                            'Applicare debounce alle sole notifiche del budget e riepilogo per ciclo; non dichiarare recupero globale dal successo di un singolo GET.')
    critical_words=('INTERVENTO NECESSARIO','TP MANCANTE','TP NON INSERITO','ORDER_QUOTE_MISMATCH','ORDER_REVIEW','RETRIES_EXHAUSTED')
    critical=[]
    for r in messages:
        text=' '.join(str(r['content'].get(k) or '') for k in ('text','caption')).upper()
        if any(w in text for w in critical_words):critical.append(r)
    if critical:finding('alerts:critical_history','warning',{'acknowledgedMessages':len(critical),'seqs':[r['seq'] for r in critical][-30:],'historical':True,'currentFaultProven':False},
                         'Conservare la priorità immediata degli errori critici; lo storico non prova che il problema sia ancora aperto. Verificare lo stato attuale nel relativo supervisore.')
    for r in read('weex_incidents.sqlite3','SELECT key,generation,state,code,last FROM incidents WHERE state=?',('ATTENTION',),optional=True):
        if not isinstance(r['last'],(int,float)) or r['last']>now:continue
        finding('alerts:persisted_attention:'+r['key'],'warning',{'incident':r,'ageSeconds':now-r['last'],
                        'meaning':'Persisted unresolved incident, not a new exchange verification'},
                        'Verificare il supervisore responsabile; non silenziare questa categoria nella riduzione degli alert.')
    if errors:finding('alerts:coverage_incomplete','warning',{'sources':errors},'Ripristinare la lettura delle fonti di audit; non interpretare dati mancanti come assenza di alert.')
    earliest=read('weex_alert_archive.sqlite3','SELECT MIN(at) AS firstAt FROM outbound_events_v1')
    first=earliest[0]['firstAt'] if earliest else None
    return {'checkedAt':datetime.fromtimestamp(now,timezone.utc).isoformat(),'auditor':'ALERT_QUALITY_LOCAL',
            'windowStart':start,'windowEnd':now,'status':'PARTIAL' if errors else 'FINDINGS' if findings else 'OK',
            'readOnly':True,'exchangeRequests':0,'telegramRequests':0,'strategyChanges':0,
            'counts':{'archiveEvents':len(archive),'attempts':len(attempts),'acknowledgedAttempts':len(sent),
                      'acknowledgedMessages':len(all_messages),'analyzedMessages':len(messages),'auditMessagesExcluded':len(all_messages)-len(messages),
                      'uncertainAttempts':len(uncertain),'pendingAttempts':len(pending),
                      'acknowledgedWithoutMessageId':sum(r['outcome'].get('messageId') is None for r in messages)},
            'coverage':{'archiveFirstAt':first,'full24HourSpanObserved':bool(first is not None and first<=start and not errors),'completeCaptureProven':False,
                        'scope':'Instrumented local outbound archive; legacy data is context only; not a full historical Telegram chat export'},
            'legacyContext':legacy,'findings':sorted(findings,key=lambda x:x['stableKey']),'errors':errors}
