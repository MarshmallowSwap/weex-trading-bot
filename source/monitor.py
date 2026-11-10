from market_agents import trend_matches
"""WEEX Futures wallet-only read-only notifications.
This service uses an isolated SQLite cursor and skips historic executions at first boot.
"""
import base64,hashlib,hmac,json,logging,sqlite3,time,urllib.request,math,re
from datetime import datetime,timezone
from contextlib import closing
from html import escape
from pathlib import Path
ROOT=Path(__file__).resolve().parent
CREDS=ROOT/"weex_credentials.json"
TG=Path(r"D:\FUNDSHOT\hyperliquid_alerts\config.json")
DB=ROOT/"events.sqlite3"
logging.basicConfig(filename=str(ROOT/"monitor.log"),level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s")
def query(path):
 c=json.loads(CREDS.read_text(encoding="utf-8"))
 ts=str(int(time.time()*1000))
 sig=base64.b64encode(hmac.new(c["secret_key"].encode(),
       (ts+"GET"+path).encode(),hashlib.sha256).digest()).decode()
 h={"ACCESS-KEY":c["api_key"],"ACCESS-SIGN":sig,
    "ACCESS-PASSPHRASE":c["passphrase"],"ACCESS-TIMESTAMP":ts,
    "Content-Type":"application/json"}
 req=urllib.request.Request("https://api-contract.weex.com"+path,headers=h)
 from weex_api_budget import open_url
 with open_url(req,timeout=20) as r:return json.load(r)
def trades():
 response=query("/capi/v3/userTrades?limit=100")
 if not isinstance(response,list):raise ValueError("Unexpected trades response")
 return sorted(response,key=lambda v:(int(v.get("time") or 0),str(v.get("id",""))))
def direction(t):
 position=str(t.get("positionSide","")).upper()
 side=str(t.get("side","")).upper()
 opening=(position=="LONG" and side=="BUY") or (position=="SHORT" and side=="SELL")
 closing=(position=="LONG" and side=="SELL") or (position=="SHORT" and side=="BUY")
 return ("open" if opening else "close" if closing else "unknown"),position
def exit_type_for_trade(t):
 # WEEX order history is authoritative when the executed order ID matches.
 oid=str(t.get("orderId",""))
 if not oid:return "NON VERIFICATO"
 try:
  result=query("/capi/v3/order/history?limit=100&page=0")
  matches=[x for x in result if str(x.get("orderId",""))==oid]
  if not matches:return "NON VERIFICATO"
  order=matches[0]
  kind=str(order.get("type","")).upper()
  if "TAKE_PROFIT" in kind or kind.startswith("TP"):return "TP"
  if "STOP" in kind or "STOP_LOSS" in kind:return "SL (BREAKEVEN N/D)"
  if kind in ("LIMIT","MARKET"):return "ORDINE "+kind
  return "NON VERIFICATO"
 except Exception:
  logging.exception("WEEX exit type lookup failed")
  return "NON VERIFICATO"

def send(t,cfg):
 from sys import path
 path.insert(0,r"D:\FUNDSHOT\hyperliquid_alerts")
 from photo import send_photo
 from weex_alert_archive import photo_sender
 send_photo=photo_sender(send_photo,ROOT,"monitor.fill",trade=t)
 action,side=direction(t)
 symbol=str(t.get("symbol","?"))
 pnl=float(t.get("realizedPnl") or 0)
 if action=="open":kind="long" if side=="LONG" else "short"
 elif action=="close" and pnl!=0:kind="profit" if pnl>0 else "loss"
 else:kind=None
 info=(f"{'🟢' if side=='LONG' else '🔴'} <b>WEEX FUTURES | {action.upper()} {escape(side)}</b>\n"
       f"━━━━━━━━━━━━━━━━━━\n"
       f"💠 <b>{escape(symbol)}</b>\n"
       f"🎯 Prezzo: <b>{escape(str(t.get('price')))} USDT</b>\n"
       f"📦 Quantità: <b>{escape(str(t.get('qty')))}</b>\n"
       f"🕒 UTC: {time.strftime('%H:%M',time.gmtime(int(t.get('time') or 0)/1000))}\n"
       + (f"💰 PnL realizzato: <b>{pnl:+.4f} USDT</b>\n" if action=='close' else "")
       + f"🔎 Esecuzione: {escape(str(t.get('id')))}")
 if kind:
  fields=([("COIN",symbol),("ENTRY",t.get("price","N/D")),
           ("SIZE",str(t.get("qty","N/D"))),("LEVA","N/D"),
           ("ORA",time.strftime("%H:%M UTC",time.gmtime(int(t.get("time") or 0)/1000)))]
          if action=="open" else
          [("COIN",symbol),("PNL",f"{pnl:+.4f} USDT"),
           ("ROI","N/D"),("EXIT",t.get("price","N/D")),("DURATA","N/D")])
  exit_type=exit_type_for_trade(t) if action=="close" else None
  send_photo(cfg,kind,fields,info+("\nEXIT TYPE: <b>"+escape(exit_type)+"</b>" if exit_type else ""),exit_type=exit_type)
 else:
  # Never downgrade a trade fill to a plain text notification.
  # Profit/loss templates would mislabel a zero-PnL close: use a neutral card.
  from weex_neutral_fill_card import render_neutral_fill
  from telegram_position_reports import send_image
  image=render_neutral_fill(t,action,side)
  caption=(f'WEEX | {action.upper()} {side} | {symbol} | '
           f'PnL fill: {pnl:+.4f} USDT. '+
           'Card neutra: il PnL del singolo fill non equivale al netto complessivo.')
  send_image(cfg,image,caption)
def candidate_report(root=ROOT,now=None):
 """Local observations only. Never requests WEEX data or authorizes an entry."""
 root=Path(root);now=time.time() if now is None else now
 def load(name):
  try:return json.loads((root/name).read_text(encoding='utf-8'))
  except (OSError,ValueError):return {}
 def fresh(stamp,seconds):
  try:return 0<=now-datetime.fromisoformat(stamp).timestamp()<=seconds
  except (TypeError,ValueError):return False
 market=load('market_agents_latest.json');source=market.get('asOf')
 empty={'sourceAt':source,'candidates':[],'ordersSubmitted':False,'exchangeRequests':0}
 if not fresh(source,720) or market.get('liveTrading') is not False:
  return {**empty,'status':'STALE','text':'WEEX • Candidate\nScansione assente o non recente: attendo nuovi dati, senza indicare vecchi segnali come attuali.'}
 cfg=load('weex_ai_risk_config.json');universe=load('universe_latest.json')
 try:
  minimum=float(cfg['risk']['minimumLeverage']);limit=int(cfg['telegramSettings']['maxConcurrentPositions']['default'])
  allowed={x['symbol'] for x in universe['symbols'] if float(x['maxLeverageAdvertised'])>=minimum}
 except (KeyError,TypeError,ValueError):
  return {**empty,'status':'CONFIG_UNAVAILABLE','text':'WEEX • Candidate\nConfigurazione o universo non disponibili: nessuna lista verificata.'}
 worker=load('weex_live_worker_latest.json')
 account_ok=(fresh(worker.get('checkedAt'),420) and worker.get('accountReadOK') is True
             and isinstance(worker.get('capacity',{}).get('count'),int))
 occupied=set(worker.get('capacity',{}).get('symbols',[])) if account_ok else set()
 skipped={}
 if fresh(worker.get('checkedAt'),420) and worker.get('checkedAt','')>=source:
  skipped={x.get('symbol'):x.get('reason') for x in worker.get('skipped',[])}
 found=[];changed=0
 for row in market.get('results',[]):
  symbol=row.get('symbol');side=row.get('marketSignal')
  if symbol not in allowed or not re.fullmatch(r'[A-Z0-9]+USDT',str(symbol)) or side not in ('LONG','SHORT') or symbol in occupied:continue
  trend=row.get('trend') or {};momentum=row.get('momentum') or {};book=row.get('realOrderBook') or {}
  if not (fresh(row.get('observedAt'),720) and fresh(book.get('receivedAt'),720)
          and trend_matches(trend,side)
          and momentum.get('confirmed') is True and book.get('passed') is True
          and book.get('depthUnitVerified') is True and book.get('status')=='OK'):continue
  try:
   volume=float(momentum['volumeRatio']);spread=float(book['spreadBps'])
   depth=min(float(book['top15BidNotional']),float(book['top15AskNotional']))
   if not all(math.isfinite(v) for v in (volume,spread,depth)) or volume<0 or not 0<=spread<=15 or depth<1000:continue
  except (KeyError,TypeError,ValueError):continue
  if skipped.get(symbol)=='SCAN_SIGNAL_CHANGED':changed+=1;continue
  found.append({'symbol':symbol,'side':side,'volumeRatio':volume,
                'finalCheckBlocked':bool(skipped.get(symbol)) and not str(skipped[symbol]).startswith('WAIT_API')})
 found.sort(key=lambda x:(-x['volumeRatio'],x['symbol']))
 try:
  with closing(sqlite3.connect('file:'+(root/'live_control.sqlite3').as_posix()+'?mode=ro',uri=True)) as db:
   mode=db.execute('SELECT mode FROM switch_v1 WHERE id=1').fetchone()[0]
 except (sqlite3.Error,TypeError):mode='UNKNOWN'
 blocks=[]
 if mode!='RUNNING':blocks.append('Trading fermo' if mode=='STOPPED' else 'Stato del trading da verificare')
 if not account_ok:blocks.append('Conto e capacità da aggiornare')
 elif worker.get('recoveryClear') is not True:blocks.append('Recupero posizioni da verificare')
 elif worker['capacity']['count']>=limit:blocks.append('Capacità occupata')
 try:
  with closing(sqlite3.connect('file:'+(root/'weex_api_budget.sqlite3').as_posix()+'?mode=ro',uri=True)) as db:
   weight=db.execute('SELECT COALESCE(SUM(weight),0) FROM api_calls_v1 WHERE at>?',(now-600,)).fetchone()[0]
   pause=db.execute("SELECT value FROM api_meta_v1 WHERE key='pause'").fetchone()
  from weex_api_budget import budget
  api=budget().used()
  recent_wait=any(str(x.get('reason','')).startswith('WAIT_API') for x in worker.get('skipped',[])) if fresh(worker.get('checkedAt'),420) else False
  if recent_wait or api.get('pauseUntil',0)>now:blocks.append('Attesa quote API WEEX')
 except sqlite3.Error:blocks.append('Budget API da verificare')
 stamp=datetime.fromisoformat(source).astimezone().strftime('%d/%m %H:%M')
 lines=['WEEX • CANDIDATE PRELIMINARI','Scansione: '+stamp]
 if found:
  for x in found[:5]:
   lines.append(f"{x['symbol']} — {x['side']} | volume {x['volumeRatio']:.2f}×"+(' | ultimo controllo finale non superato' if x['finalCheckBlocked'] else ''))
  if len(found)>5:lines.append(f'Altre {len(found)-5} candidate nella scansione.')
  lines.append('Superati nella scansione: trend, momentum e book con unità verificate.')
 else:lines.append('Nessuna coppia libera con tutti i controlli preliminari superati.')
 if changed:lines.append(f'{changed} segnali esclusi: cambiati al controllo successivo del runner.')
 lines.append('LIVE: '+('abilitato' if mode=='RUNNING' else 'fermo' if mode=='STOPPED' else 'da verificare'))
 if blocks:lines.append('Attese: '+'; '.join(blocks)+'.')
 lines.append('Prima di aprire il runner ricontrolla segnale, book, saldo, leva, quantità e commissioni. Questo avviso non conferma un ordine.')
 return {**empty,'status':'CANDIDATES' if found else 'NO_CANDIDATES','candidates':found,
         'blocks':blocks,'liveMode':mode,'text':'\n'.join(lines)}

def send_candidate_text(text,cfg):
 body=json.dumps({'chat_id':cfg['telegram_chat_id'],'text':text}).encode('utf-8')
 request=urllib.request.Request('https://api.telegram.org/bot'+cfg['telegram_bot_token']+'/sendMessage',body,{'Content-Type':'application/json'})
 from weex_alert_archive import observed
 def dispatch():
  with urllib.request.urlopen(request,timeout=20) as response:result=json.load(response)
  if result.get('ok') is not True:raise RuntimeError('CANDIDATE_TELEGRAM_SEND_FAILED')
  return result
 result=observed(ROOT,'monitor.notification','sendMessage',{'text':text},dispatch)
 return result['result']['message_id']

def notify_candidates(conn,cfg,root=ROOT,now=None,sender=None):
 report=candidate_report(root,now)
 if not report['candidates']:return {'status':report['status'],'sent':False}
 conn.execute('CREATE TABLE IF NOT EXISTS candidate_alerts_v1(source_at TEXT PRIMARY KEY,status TEXT,updated_at REAL,message_id INTEGER)')
 # Reserve before sending. An uncertain transport outcome is not blindly replayed.
 with conn:
  inserted=conn.execute('INSERT OR IGNORE INTO candidate_alerts_v1 VALUES(?,?,?,NULL)',(report['sourceAt'],'SENDING',time.time())).rowcount
 if not inserted:return {'status':'ALREADY_HANDLED','sent':False}
 try:
  message_id=(sender or send_candidate_text)(report['text'],cfg)
 except Exception as exc:
  with conn:conn.execute('UPDATE candidate_alerts_v1 SET status=?,updated_at=? WHERE source_at=?',('DELIVERY_UNCERTAIN',time.time(),report['sourceAt']))
  logging.warning('Candidate delivery uncertain (%s); use /candidates for current list',type(exc).__name__)
  return {'status':'DELIVERY_UNCERTAIN','sent':False}
 with conn:conn.execute('UPDATE candidate_alerts_v1 SET status=?,updated_at=?,message_id=? WHERE source_at=?',('SENT',time.time(),message_id,report['sourceAt']))
 return {'status':'SENT','sent':True,'candidateCount':len(report['candidates']),'messageId':message_id}

def candidate_notification_tick(conn):
 # Independent of the fills request: WEEX budget deferrals must not suppress alerts.
 try:return notify_candidates(conn,json.loads(TG.read_text(encoding='utf-8')))
 except Exception as exc:
  logging.warning('Candidate notification check failed (%s)',type(exc).__name__)
  return {'status':'ERROR','sent':False}

def scan_notification_tick(conn):
 try:
  from weex_scan_notifications import drain
  cfg=json.loads(TG.read_text(encoding='utf-8'))
  from weex_service_health import tick
  tick(ROOT,lambda text:send_candidate_text(text,cfg))
  from weex_quality_auditors import drain as drain_quality
  drain_quality(ROOT,lambda text:send_candidate_text(text,cfg))
  delivered=drain(conn,cfg,send_candidate_text)
  try:
   from weex_telegram_cleanup import tick as cleanup_tick
   cleanup_tick(ROOT,cfg)
  except Exception as exc:
   logging.warning('Telegram cleanup unavailable (%s)',type(exc).__name__)
  try:
   from weex_fill_alerts import drain as drain_orders
   drain_orders(conn,ROOT,cfg)
  except Exception as exc:
   logging.warning('Aggregated fill alert unavailable (%s)',type(exc).__name__)
  return delivered
 except Exception as exc:
  logging.warning('Scan notification check failed (%s)',type(exc).__name__)
  return []

def main():
 conn=sqlite3.connect(DB)
 conn.execute("CREATE TABLE IF NOT EXISTS events (id TEXT PRIMARY KEY, status TEXT NOT NULL)")
 conn.execute("CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
 conn.commit()
 print("WEEX watcher: fills every 60s, scan alerts every 2s",flush=True)
 next_fills=0
 while True:
  scan_notification_tick(conn)
  if time.monotonic()<next_fills:
   time.sleep(2);continue
  next_fills=time.monotonic()+60
  try:
   current=trades()
   already=conn.execute("SELECT value FROM state WHERE key='initialized'").fetchone()
   if not already:
    for t in current:conn.execute("INSERT OR IGNORE INTO events VALUES (?,?)",(str(t["id"]),"baseline"))
    conn.execute("INSERT OR REPLACE INTO state VALUES ('initialized','1')")
    conn.commit()
    logging.info("WEEX baseline initialized (%d executions)",len(current))
   else:
    cfg=json.loads(TG.read_text(encoding="utf-8"))
    from weex_fill_alerts import ingest
    ingest(conn,current)
   print(time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime()),"WEEX heartbeat count",len(current),flush=True)
  except Exception:
   logging.exception("WEEX polling error")
  candidate_notification_tick(conn)
  time.sleep(2)
if __name__=="__main__":main()
