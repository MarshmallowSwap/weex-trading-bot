"""Persistent Telegram outbox for public scanner lifecycle events. No WEEX calls."""
import json,sqlite3,time
from collections import Counter
from contextlib import closing
from datetime import datetime,timezone
from pathlib import Path

def schema(c):
 c.execute('''CREATE TABLE IF NOT EXISTS scan_notifications_v1(
 id TEXT PRIMARY KEY,cycle TEXT,kind TEXT,created REAL,text TEXT,status TEXT,message_id INTEGER)''');c.commit()

def enqueue(root,cycle,kind,text,created=None):
 with closing(sqlite3.connect(Path(root)/'events.sqlite3',timeout=5)) as c:
  schema(c)
  with c:c.execute('INSERT OR IGNORE INTO scan_notifications_v1 VALUES(?,?,?,?,?,?,NULL)',
     (cycle+'|'+kind,cycle,kind,time.time() if created is None else created,text,'PENDING'))

def local_time(stamp):return datetime.fromisoformat(stamp).astimezone().strftime('%H:%M:%S')

def started(root,cycle):
 try:
  cfg=json.loads((Path(root)/'weex_ai_risk_config.json').read_text(encoding='utf-8'))
  universe=json.loads((Path(root)/'universe_latest.json').read_text(encoding='utf-8'))
  floor=cfg['risk']['minimumLeverage'];count=sum(x['maxLeverageAdvertised']>=floor for x in universe['symbols'])
  scope=f'{count} coppie previste | leva da {floor}x'
 except (OSError,ValueError,KeyError,TypeError):scope='Verifica universo coppie in corso'
 enqueue(root,cycle,'START',f'WEEX - SCANSIONE AVVIATA\nOre {local_time(cycle)}\n{scope}\nTi invio l\'esito al termine.')

def finished(root,cycle,result):
 rows=result['results'];signals=[x for x in rows if x.get('marketSignal') in ('LONG','SHORT')]
 passed=[x for x in signals if (x.get('realOrderBook') or {}).get('passed') is True and (x.get('realOrderBook') or {}).get('depthUnitVerified') is True]
 errors=sum(x.get('decision')=='ERROR' for x in rows)
 complete=result.get('analysisComplete') is True
 title='SCANSIONE CONCLUSA' if complete else 'SCANSIONE INCOMPLETA'
 lines=[f'WEEX - {title}',f"Ore {local_time(result['asOf'])} | durata {result['durationSeconds']:.0f}s",
        f"Analizzate: {len(rows)-errors}/{result['universeSize']} coppie",
        f'Segnali strategia: {len(signals)}',f'Segnali con book verificato: {len(passed)}']
 if passed:
  ranked=sorted(passed,key=lambda x:x.get('momentum',{}).get('volumeRatio',0),reverse=True)
  lines.append(' | '.join(x['symbol']+' '+x['marketSignal'] for x in ranked[:5]))
  if len(passed)>5:lines.append(f'Altri segnali con book verificato: {len(passed)-5}')
 blocks=Counter(reason for x in signals for reason in (x.get('realOrderBook') or {}).get('vetoReasons',[]))
 labels={'DEPTH_UNITS_UNVERIFIED':'unita book da verificare','SPREAD_TOO_WIDE':'spread elevato','INSUFFICIENT_BOOK_DEPTH':'liquidita insufficiente','ORDERBOOK_UNAVAILABLE':'book non disponibile'}
 if blocks:lines.append('Blocchi: '+', '.join(f'{labels.get(k,k)} {v}' for k,v in blocks.items()))
 if errors:lines.append(f'Errori analisi: {errors}')
 if result.get('booksUnavailable'):lines.append(f"Book non acquisiti: {result['booksUnavailable']}")
 if not signals and not errors:lines.append('Nessun segnale valido in questo ciclo.')
 lines.append('Esito della scansione: gli ingressi richiedono ancora i controlli finali del runner.')
 enqueue(root,cycle,'FINISH','\n'.join(lines))

def failed(root,cycle,exc):
 from weex_api_budget import BudgetDeferred
 if isinstance(exc,BudgetDeferred):
  enqueue(root,cycle,'FINISH',f'WEEX - SCANSIONE IN ATTESA\nAvvio {local_time(cycle)}\nBudget API o recupero letture temporaneamente non disponibile.\nNessun esito completo; ripresa subordinata al budget e al supervisore.')
  return
 # Exception text may contain URLs or other untrusted information: type only.
 enqueue(root,cycle,'FINISH',f'WEEX - SCANSIONE INTERROTTA\nAvvio {local_time(cycle)}\nErrore: {type(exc).__name__}\nNessun esito completo disponibile; nuovo tentativo al prossimo ciclo.')

def drain(conn,cfg,sender,now=None):
 now=time.time() if now is None else now;schema(conn)
 # A killed scanner cannot emit FINISH. Alert once without inventing an outcome.
 orphaned=conn.execute('''SELECT cycle,created FROM scan_notifications_v1 a WHERE kind='START'
 AND created>? AND created<=? AND NOT EXISTS(SELECT 1 FROM scan_notifications_v1 b
 WHERE b.cycle=a.cycle AND b.kind IN ('FINISH','TIMEOUT'))''',(now-720,now-300)).fetchall()
 with conn:
  for cycle,created in orphaned:
   conn.execute('INSERT OR IGNORE INTO scan_notifications_v1 VALUES(?,?,?,?,?,?,NULL)',
    (cycle+'|TIMEOUT',cycle,'TIMEOUT',now,'WEEX - ESITO SCANSIONE NON RICEVUTO\nAvvio '+local_time(cycle)+'\nSono trascorsi oltre 5 minuti: la scansione potrebbe essere interrotta.','PENDING'))
  conn.execute("UPDATE scan_notifications_v1 SET status='EXPIRED' WHERE status='PENDING' AND created<?",(now-720,))
 rows=conn.execute("SELECT id,text FROM scan_notifications_v1 WHERE status='PENDING' ORDER BY created,CASE kind WHEN 'START' THEN 0 ELSE 1 END,id LIMIT 4").fetchall()
 results=[]
 for ident,text in rows:
  with conn:
   reserved=conn.execute("UPDATE scan_notifications_v1 SET status='SENDING' WHERE id=? AND status='PENDING'",(ident,)).rowcount
  if not reserved:continue
  try:message_id=sender(text,cfg)
  except Exception:
   with conn:conn.execute("UPDATE scan_notifications_v1 SET status='DELIVERY_UNCERTAIN' WHERE id=?",(ident,))
   results.append({'id':ident,'status':'DELIVERY_UNCERTAIN'});continue
  with conn:conn.execute("UPDATE scan_notifications_v1 SET status='SENT',message_id=? WHERE id=?",(message_id,ident))
  results.append({'id':ident,'status':'SENT','messageId':message_id})
 return results
