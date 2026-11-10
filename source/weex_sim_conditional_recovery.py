"""Fail-closed restart/partial-fill audit for WEEX conditional TP+SL.

Offline-only, accepts trusted GET snapshots; never sends, retries,
cancels or changes orders. Persisted state survives process restart.
No assertion that a pair is atomic/OCO merely because both are present.
"""
import hashlib,json,sqlite3
from contextlib import closing
from decimal import Decimal
from weex_tp_limit_shadow import decimal

def _json(x):return json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False)
def _conn(path):
    db=sqlite3.connect(path,timeout=5)
    db.row_factory=sqlite3.Row
    db.execute('PRAGMA synchronous=FULL')
    db.execute('''CREATE TABLE IF NOT EXISTS conditional_recovery_v1 (
       trade_id TEXT PRIMARY KEY, intent_hash TEXT NOT NULL,
       intent_json TEXT NOT NULL, state TEXT NOT NULL,
       max_closed TEXT NOT NULL, last_evidence TEXT)''')
    return db

def register(path,trade_id,*,position_id,symbol,side,entry_quantity,
             tp_client_id,sl_client_id,entry_cost,entry_fees):
    if not trade_id or not position_id or not symbol or side not in ('LONG','SHORT'):
        raise ValueError('INVALID_TRADE_BINDING')
    q=decimal(entry_quantity);cost=decimal(entry_cost);fees=decimal(entry_fees)
    if q<=0 or cost<=0 or fees<0 or not tp_client_id or not sl_client_id or tp_client_id==sl_client_id:
        raise ValueError('INVALID_INTENT')
    intent={'tradeId':str(trade_id),'positionId':str(position_id),
            'symbol':symbol,'side':side,'quantity':str(q),'entryCost':str(cost),
            'entryFees':str(fees),'tpClientId':tp_client_id,'slClientId':sl_client_id}
    h=hashlib.sha256(_json(intent).encode()).hexdigest()
    with closing(_conn(path)) as db,db:
        prior=db.execute('SELECT intent_hash,state FROM conditional_recovery_v1 WHERE trade_id=?',
                         (str(trade_id),)).fetchone()
        if prior:
            if prior['intent_hash']!=h:raise ValueError('RESTART_INTENT_CHANGED')
            return {'state':prior['state'],'existing':True,'actionsAllowed':False}
        db.execute('INSERT INTO conditional_recovery_v1 VALUES (?,?,?,?,?,NULL)',
                   (str(trade_id),h,_json(intent),'PREPARED_NOT_CERTIFIED','0'))
    return {'state':'PREPARED_NOT_CERTIFIED','existing':False,'actionsAllowed':False}

def observe(path,trade_id,*,positions,algos,regular_orders,exit_fills,source_confirmed=False):
    """Every snapshot must originate from same authenticated simulation GET session."""
    base={'state':'REVIEW_REQUIRED','actionsAllowed':False,'canRetry':False,
          'ocoCertified':False,'stopLossCoverageCertified':False}
    with closing(_conn(path)) as db,db:
        rec=db.execute('SELECT * FROM conditional_recovery_v1 WHERE trade_id=?',
                       (str(trade_id),)).fetchone()
        if rec is None:raise ValueError('UNKNOWN_RECOVERY_TRADE')
        intent=json.loads(rec['intent_json'])
        try:
            if not source_confirmed:raise ValueError('EXCHANGE_READBACK_NOT_CONFIRMED')
            if any(not isinstance(x,list) for x in (positions,algos,regular_orders,exit_fills)):
                raise ValueError('INCOMPLETE_SNAPSHOTS')
            if any(not isinstance(x,dict) for rows in (positions,algos,regular_orders,exit_fills) for x in rows):
                raise ValueError('INVALID_SNAPSHOT_ROW')
            own=[p for p in positions if str(p.get('id'))==intent['positionId']]
            if len(own)>1:raise ValueError('DUPLICATED_POSITION_ID')
            if own and (own[0].get('symbol')!=intent['symbol'] or own[0].get('side')!=intent['side']):
                raise ValueError('POSITION_IDENTITY_CONFLICT')
            rem=decimal(own[0].get('size')) if own else Decimal(0)
            total=decimal(intent['quantity'])
            if rem<0 or rem>total:raise ValueError('UNEXPECTED_POSITION_SIZE')
            # Independently verified fills require unique IDs, consistent direction and
            # matching position identity; never infer them from TP order status.
            ids=set();filled=Decimal(0);proceeds=Decimal(0);exit_fee=Decimal(0)
            for f in exit_fills:
                fid=f.get('id')
                if not fid or str(fid) in ids:raise ValueError('DUPLICATE_FILL_ID')
                ids.add(str(fid))
                if (str(f.get('positionId'))!=intent['positionId']
                        or f.get('symbol')!=intent['symbol']
                        or f.get('positionSide')!=intent['side']
                        or f.get('side')!=('SELL' if intent['side']=='LONG' else 'BUY')
                        or f.get('commissionAsset')!='USDT'):
                    raise ValueError('UNBOUND_EXIT_FILL')
                size=decimal(f.get('qty'));price=decimal(f.get('price'));fee=decimal(f.get('commission'))
                if size<=0 or price<=0 or fee<0:raise ValueError('INVALID_EXIT_FILL')
                filled+=size;proceeds+=size*price;exit_fee+=fee
            if filled+rem!=total:raise ValueError('FILLS_AND_REMAINING_DISAGREE')
            if filled<decimal(rec['max_closed']):raise ValueError('RESTART_FILL_REGRESSION')
            if any(o.get('symbol')==intent['symbol'] for o in regular_orders):
                raise ValueError('UNKNOWN_REGULAR_ORDER')
            matches={}
            for typ,field in (('TP','tpClientId'),('SL','slClientId')):
                found=[a for a in algos if a.get('clientAlgoId')==intent[field]]
                if len(found)>1:raise ValueError('DUPLICATE_'+typ+'_ORDER')
                matches[typ]=found[0] if found else None
                if found:
                    a=found[0]
                    if (a.get('symbol')!=intent['symbol'] or a.get('positionSide')!=intent['side']
                        or a.get('side')!=('SELL' if intent['side']=='LONG' else 'BUY')
                        or a.get('reduceOnly') is not True
                        or a.get('algoStatus') not in ('NEW','UNTRIGGERED')):
                        raise ValueError(typ+'_ORDER_CHANGED_OR_INACTIVE')
                    if decimal(a.get('quantity')) != total:
                        raise ValueError(typ+'_ORDER_QUANTITY_CHANGED')
                    expected_types = ('TAKE_PROFIT','TAKE_PROFIT_LIMIT') if typ=='TP' else (
                        'STOP_LOSS','STOP_LOSS_MARKET','STOP_MARKET')
                    if a.get('orderType') not in expected_types:
                        raise ValueError(typ+'_ORDER_TYPE_UNVERIFIED')
                    if typ=='TP':
                        price=a.get('price',a.get('executePrice'))
                        if price is None or decimal(price)<=0:
                            raise ValueError('TP_LIMIT_EXECUTION_PRICE_UNVERIFIED')
                    else:
                        price=a.get('price',a.get('executePrice'))
                        if price is not None and decimal(price)!=0:
                            raise ValueError('STOP_MARKET_EXECUTION_UNVERIFIED')
            if rem==0:
                if any(matches.values()):raise ValueError('ORPHANED_EXITS_AFTER_CLOSE')
                state='CLOSED_READBACK_NO_OCO_PROOF'
            elif rem<total:
                # Verified on WEEX SIM V3 (2026-11-04): a 0.0002 BTC
                # position partially closed to 0.0001 BTC retained BOTH
                # 0.0002 BTC TP and SL conditional quantities UNTRIGGERED.
                # Never infer that WEEX auto-resizes remaining protection.
                state='PARTIAL_RECONCILIATION_REQUIRED'
            elif not matches['TP'] or not matches['SL']:
                state='MISSING_PROTECTION_REVIEW'
            else:
                state='BOTH_ALGOS_OBSERVED_NOT_OCO_CERTIFIED'
            fraction=filled/total
            gross= (proceeds-decimal(intent['entryCost'])*fraction) if intent['side']=='LONG' else (
                     decimal(intent['entryCost'])*fraction-proceeds)
            net=gross-decimal(intent['entryFees'])*fraction-exit_fee
            protection_oversized=(rem>0 and any(
                matches[k] is not None and decimal(matches[k].get('quantity'))>rem
                for k in ('TP','SL')))
            evidence={'closedQuantity':str(filled),'remainingQuantity':str(rem),
                      'realizedNetBeforeFundingUSDT':str(net),
                      'fundingIncluded':False,'snapshotValidated':True,
                      'protectionOversized':protection_oversized,
                      'riskReason':('STALE_TP_SL_QUANTITY_AFTER_PARTIAL'
                                    if protection_oversized else None),
                      'needsExitOrderReconciliation':rem<total}
            db.execute('UPDATE conditional_recovery_v1 SET state=?,max_closed=?,last_evidence=? WHERE trade_id=?',
                       (state,str(filled),_json(evidence),str(trade_id)))
            return {**base,'state':state,'evidence':evidence}
        except (ValueError,KeyError,TypeError,ArithmeticError) as exc:
            return {**base,'reason':str(exc)}
