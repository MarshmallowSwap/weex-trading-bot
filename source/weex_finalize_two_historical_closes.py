"""Finalize two historically closed WEEX bot trades, local SQLite ONLY.

Requires exact historical fills and bot/external TP proof; full fresh account
flat; STOPPED live control; exclusive worker lock; SQLite backup; one atomic
transaction with ownership/identity compare. NO exchange writes, no retries.
"""
import json,hashlib,sqlite3
from pathlib import Path
from contextlib import closing
from datetime import datetime,timezone
from weex_execution_cycle import exclusive
from weex_lifecycle import Lifecycle,now,dump
from weex_live_worker import Reader,ROOT
from weex_qnt_offline_proof_recheck import check as qnt_check
from weex_ltc_external_tp_proof import run as ltc_check
from live_control import state
LTC='wxentry_1566be92f4fe10fdd0b83ca3'
QNT='wxentry_7f327b721a398e3e86033c73'
IDS={LTC:'LTCUSDT',QNT:'QNTUSDT'}
def certified(qnt,ltc):
 if qnt.get('state')!='HISTORICAL_BOT_TP_PROOF_REVALIDATED' or qnt.get('symbol')!='QNTUSDT':
  raise ValueError('QNT_PROOF_NOT_VERIFIED')
 if qnt.get('targetMetBeforeFunding') is not False or not qnt.get('proofSha256'):
  raise ValueError('QNT_PROOF_INCOMPLETE')
 if ltc.get('status')!='EXTERNAL_TP_HISTORICAL_CLOSE_VERIFIED' or ltc.get('symbol')!='LTCUSDT':
  raise ValueError('LTC_PROOF_NOT_VERIFIED')
 if ltc.get('botTPUsed') is not False or ltc.get('stillNotBotTP') is not True:
  raise ValueError('LTC_WRONG_OWNERSHIP')
 if not ltc.get('flatAccountConfirmed') or not ltc.get('evidenceSha256'):
  raise ValueError('LTC_FLAT_OR_EVIDENCE_UNVERIFIED')
 if ltc.get('targetMetBeforeFunding') is not False:
  raise ValueError('LTC_ECONOMIC_PROOF_INCOMPLETE')
 return True

def finalize(root=ROOT):
 root=Path(root)
 result={'status':'BLOCKED','liveWrites':0,'liveActivated':False,
         'journalUpdated':False,'trades':[]}
 with exclusive(root/'weex_live_worker.lock'):
  if state(root)['mode']!='STOPPED':return {**result,'reason':'LIVE_NOT_STOPPED'}
  qnt=qnt_check()
  if qnt.get('state')!='HISTORICAL_BOT_TP_PROOF_REVALIDATED':
   return {**result,'reason':'QNT_PROOF_NOT_VERIFIED'}
  ltc=ltc_check(persist_evidence=True)
  certified(qnt,ltc)
  # One fresh complete account observation AFTER all historical reads.
  p,o,a=Reader(root).account()
  if p or o or a:return {**result,'reason':'ACCOUNT_NOT_FLAT_OR_ORDERS_PRESENT'}
  if state(root)['mode']!='STOPPED':return {**result,'reason':'LIVE_CHANGED'}
  engine=Lifecycle(root/'weex_user_live_lifecycle.sqlite3',None,lambda:{})
  qnt_detail_path=root/'weex_reconcile_details'/(
      hashlib.sha256(QNT.encode()).hexdigest()+'.json')
  qnt_evidence=json.loads(qnt_detail_path.read_text(encoding='utf-8'))
  if (qnt_evidence.get('proof',{}).get('evidenceSha256')!=qnt['proofSha256']
      or qnt_evidence.get('tradeId')!=QNT):
   raise ValueError('QNT_STORED_EVIDENCE_CHANGED')
  ltc_evidence=json.loads((root/'weex_ltc_verified_close_evidence.json').read_text(encoding='utf-8'))
  if (ltc_evidence.get('report',{}).get('evidenceSha256')!=ltc['evidenceSha256']
      or hashlib.sha256(json.dumps(ltc_evidence['raw'],sort_keys=True).encode()).hexdigest()!=ltc['evidenceSha256']):
   raise ValueError('LTC_STORED_EVIDENCE_CHANGED')
  now_iso=datetime.now(timezone.utc).isoformat()
  qnt_detail={**qnt_evidence['proof'],'currentFlatAccountConfirmed':True,
     'residualOrdersAbsent':True,'reconciledAtUTC':now_iso,
     'reconciledBy':'EXACT_TWO_TRADE_HISTORICAL_RECONCILIATION'}
  ltc_detail={'resolution':'CLOSED_EXTERNAL_WEEX_HISTORY',
     'externalConditionalTP':True,'externalMarketClose':False,
     'botTPUsed':False,'entryOrderId':ltc_evidence['raw']['entry']['orderId'],
     'exitOrderIds':[ltc['exitOrderId']],'quantity':ltc['closedQuantity'],
     'actualExitValueUSDT':ltc['actualExitValueUSDT'],
     'actualExitFeesUSDT':ltc['actualExitFeesUSDT'],
     'realizedNetBeforeFundingUSDT':ltc['netBeforeFundingUSDT'],
     'fundingIncluded':False,'targetMetBeforeFunding':False,
     'evidenceSha256':ltc['evidenceSha256'],
     'currentFlatAccountConfirmed':True,'residualOrdersAbsent':True,
     'reconciledAtUTC':now_iso,
     'reconciledBy':'EXACT_TWO_TRADE_HISTORICAL_RECONCILIATION'}
  planned={QNT:(qnt_detail,qnt_evidence),LTC:(ltc_detail,ltc_evidence)}
  db=root/'weex_user_live_lifecycle.sqlite3'
  backup_dir=root/'reconciliation_backups';backup_dir.mkdir(exist_ok=True)
  backup=backup_dir/('before-exact-close-'+str(now())+'.sqlite3')
  with closing(sqlite3.connect(db)) as src,closing(sqlite3.connect(backup)) as dst:
   src.backup(dst)
  with closing(engine.db()) as c:
   c.execute('BEGIN IMMEDIATE')
   try:
    rows={x['id']:x for x in c.execute(
      'SELECT * FROM trades_v1 WHERE id IN (?,?)',(LTC,QNT))}
    if set(rows)!=set(IDS):raise ValueError('TRADE_ROWS_MISSING')
    for tid,expected_symbol in IDS.items():
     row=rows[tid]
     if row['symbol']!=expected_symbol or row['state'] not in ('RECONCILIATION_PENDING','REVIEW_REQUIRED'):
      raise ValueError('TRADE_STATE_OR_IDENTITY_CHANGED')
     owned=json.loads(row['owned'] or '{}')
     if str(owned.get('entryOrderId'))!=str(planned[tid][0]['entryOrderId']):
      raise ValueError('ENTRY_ORDER_ID_CHANGED')
     if any(w['state'] not in ('RESPONSE_RECEIVED','NOT_SENT') for w in
            c.execute('SELECT state FROM writes_v1 WHERE trade_id=?',(tid,))):
      raise ValueError('UNCERTAIN_LOCAL_WRITE')
    c.execute('''CREATE TABLE IF NOT EXISTS external_close_evidence_v1(
      trade_id TEXT PRIMARY KEY,proof_sha256 TEXT NOT NULL,proof TEXT NOT NULL,
      previous_record TEXT NOT NULL,recorded_at INTEGER NOT NULL)''')
    for tid,(detail,evidence) in planned.items():
     previous=dict(rows[tid]);stamp=now()
     c.execute('INSERT INTO external_close_evidence_v1 VALUES(?,?,?,?,?)',
       (tid,detail['evidenceSha256'],dump(evidence),dump(previous),stamp))
     c.execute('UPDATE trades_v1 SET state=?,detail=?,updated=? WHERE id=?',
       ('CLOSED',dump(detail),stamp,tid))
     engine.event(c,tid,'CLOSED',detail)
    if state(root)['mode']!='STOPPED':raise ValueError('CONTROL_CHANGED_AT_COMMIT')
    c.commit()
   except BaseException:
    c.rollback();raise
  return {**result,'status':'TWO_HISTORICAL_CLOSES_RECONCILED',
      'journalUpdated':True,'accountFlat':True,'backupCreated':backup.exists(),
      'trades':[{'symbol':IDS[t],'state':'CLOSED',
                 'resolution':planned[t][0]['resolution'],
                 'netBeforeFundingUSDT':planned[t][0]['realizedNetBeforeFundingUSDT'],
                 'targetMetBeforeFunding':False} for t in (LTC,QNT)]}
if __name__=='__main__':
 try:print(json.dumps(finalize()))
 except Exception as exc:
  print(json.dumps({'status':'BLOCKED','errorType':type(exc).__name__,
      'reason':str(exc) if isinstance(exc,ValueError) else None,
      'liveWrites':0,'journalUpdated':False}))
