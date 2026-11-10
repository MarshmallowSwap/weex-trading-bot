"""Read-only Telegram position reports. No order or live-control capabilities."""
import json, sqlite3, time, os
from contextlib import closing
from decimal import Decimal as D
from pathlib import Path
from urllib.parse import urlencode

DAY=86400000
ROOT=Path(__file__).resolve().parent

def number(value):
    n=D(str(value))
    if not n.is_finite():raise ValueError('INVALID_NUMBER')
    return n

def real_symbol(symbol):
    return isinstance(symbol,str) and symbol.endswith('USDT') and not symbol.endswith('SUSDT') and symbol.isalnum()

def live_positions(rows):
    if not isinstance(rows,list):raise ValueError('POSITION_SCHEMA')
    result=[];seen=set()
    for p in rows:
        if not isinstance(p,dict):raise ValueError('POSITION_SCHEMA')
        if not real_symbol(p.get('symbol')):continue
        if p.get('asset')!='USDT' or p.get('side') not in ('LONG','SHORT'):raise ValueError('POSITION_SCHEMA')
        qty=number(p['size'])
        if qty<0:raise ValueError('NEGATIVE_POSITION')
        if not qty:continue
        key=str(p['id'])
        if key in seen:raise ValueError('DUPLICATE_POSITION')
        seen.add(key);result.append(p)
    return result

def bot_tp_previews(root):
    """Exact bot-owned position ID -> validated saved TP PnL preview; read-only."""
    path=Path(root)/'weex_user_live_lifecycle.sqlite3'
    if not path.exists():return {}
    result={}
    with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True,timeout=3)) as c:
        for symbol,state,owned in c.execute("SELECT symbol,state,owned FROM trades_v1 WHERE state='PROTECTED' AND owned IS NOT NULL"):
            data=json.loads(owned)
            preview=data.get('tpPnlPreview') or {}
            if preview.get('mode')!='PNL_GROSS_BEFORE_COSTS_USDT':continue
            if not all(k in preview for k in ('targetGrossUSDT','estimatedNetAfterFeesSlippageUSDT','triggerPrice')):continue
            if (not data.get('positionId') or data.get('tpRequest',{}).get('triggerPrice')!=preview['triggerPrice']
                or not data.get('quantity') or not data.get('actualEntryCostUSDT')
                or not data.get('actualEntryFeesUSDT')):continue
            key=(symbol,str(data['positionId']))
            if key in result:raise ValueError('AMBIGUOUS_BOT_POSITION_PREVIEW')
            result[key]={**preview,'ownedQuantity':data['quantity'],
                         'ownedEntryCostUSDT':data['actualEntryCostUSDT'],
                         'ownedEntryFeesUSDT':data['actualEntryFeesUSDT'],
                         'ownedTpRequest':data['tpRequest']}
    return result


def open_rows(positions,algos,trailing=None,tp_previews=None):
    from weex_capacity import full_closing_tp
    from weex_trailing import merge
    algos=merge(algos,trailing or [])
    result=[]
    if not isinstance(algos,list):raise ValueError('ALGO_SCHEMA')
    for p in live_positions(positions):
        matches=[a for a in algos if a.get('symbol')==p['symbol'] and a.get('positionSide')==p['side']
                 and a.get('side')==('SELL' if p['side']=='LONG' else 'BUY')
                 and a.get('reduceOnly') is True and a.get('orderType') in ('TAKE_PROFIT_MARKET','TRAILING_MARKET')
                 and a.get('algoStatus') in ('NEW','UNTRIGGERED')]
        unique=sum(x['symbol']==p['symbol'] and x['side']==p['side'] for x in positions)==1
        tp=[]
        for a in matches:
            price=number(a['triggerPrice'])
            if price<=0:raise ValueError('TP_PRICE')
            trigger={'MARK_PRICE':'Mark','CONTRACT_PRICE':'Last'}.get(a.get('workingType'),'trigger N/D')
            coverage='totale' if unique and full_closing_tp(a,[p]) else 'parziale / da verificare'
            if a.get('orderType')=='TRAILING_MARKET':
                callback=number(a['callbackRate'])*100
                estimate=number(p['size'])*number(p.get('markPrice') or price)*number(a['callbackRate'])
                tp.append(f'Trailing: attivazione {price:f} | rientro {callback:f}% (~{estimate:.2f} USDT) | {trigger} | {coverage}')
            else:tp.append(f'{price:f} | {trigger} | {coverage}')
        q=number(p['size']);pnl=number(p['unrealizePnl']) if p.get('unrealizePnl') is not None else None
        row={'symbol':p['symbol'],'side':p['side'],'quantity':str(q),'leverage':str(number(p['leverage'])),
             'entry':str(number(p['openValue'])/q),'pnl':str(pnl) if pnl is not None else None,
             'tp':tp or ['ASSENTE: nessun TP market attivo verificato'],'margin':p.get('marginType','N/D')}
        preview=(tp_previews or {}).get((p['symbol'],str(p['id'])))
        expected=preview.get('ownedTpRequest') if preview else None
        matched=[a for a in matches if a.get('triggerPrice')==preview.get('triggerPrice')] if preview else []
        if (preview and expected and len(matches)==1 and len(matched)==1 and unique
            and number(preview['ownedQuantity'])==q
            and number(preview['ownedEntryCostUSDT'])==number(p['openValue'])
            and ('openFee' not in p or number(preview['ownedEntryFeesUSDT'])==number(p['openFee']))
            and expected.get('symbol')==p['symbol'] and expected.get('positionSide')==p['side']
            and expected.get('triggerPrice')==matched[0].get('triggerPrice')
            and expected.get('triggerPriceType')==matched[0].get('workingType')
            and expected.get('quantity') is not None
            and number(expected['quantity'])==q and expected.get('reduceOnly') is True
            and full_closing_tp(matched[0],[p])):
            row['tpGrossTargetUSDT']=str(number(preview['targetGrossUSDT']))
            row['tpNetEstimatedUSDT']=str(number(preview['estimatedNetAfterFeesSlippageUSDT']))
            row['tpNetEstimateScope']='AL_TRIGGER_PRIMA_FUNDING_NON_GARANTITO'
        result.append(row)
    return sorted(result,key=lambda x:(x['symbol'],x['side']))

def journal_metadata(root):
    """Read only; missing metadata must never invent historical leverage or TP."""
    path=Path(root)/'weex_user_live_lifecycle.sqlite3'
    if not path.exists():return []
    with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True,timeout=3)) as c:
        c.row_factory=sqlite3.Row
        records=[]
        for r in c.execute("SELECT symbol,state,plan,owned,detail,id FROM trades_v1 WHERE state='CLOSED' OR owned IS NOT NULL"):
            v=dict(r)
            for k in ('plan','owned','detail'):v[k]=json.loads(v[k]) if v[k] else {}
            records.append(v)
        for r in records:
            r['exitIds']=[str(r['detail']['exitOrderId'])] if r['detail'].get('exitOrderId') else []
            # An acknowledged TP ID can identify the historical order even if
            # the separate execution worker is still reconciling its closure.
            for w in c.execute("SELECT payload,response FROM writes_v1 WHERE trade_id=? AND kind='TP' AND state='RESPONSE_RECEIVED'",(r['id'],)):
                payload=json.loads(w[0]);response=json.loads(w[1]) if w[1] else None
                if isinstance(response,dict):response=[response]
                if payload==r['owned'].get('tpRequest') and isinstance(response,list) and len(response)==1:
                    ack=response[0]
                    if ack.get('success') is True and ack.get('orderId'):r['exitIds'].append(str(ack['orderId']))
        # External TP closure evidence is distinct from a bot-owned TP request.
        if c.execute("SELECT 1 FROM sqlite_master WHERE name='external_close_evidence_v1'").fetchone():
            proofs={r[0]:json.loads(r[1]) for r in c.execute('SELECT trade_id,proof FROM external_close_evidence_v1')}
            for r in records:
                if r['id'] in proofs:
                    proof=proofs[r['id']]
                    r['externalOrder']=proof.get('exitOrder',{})
                    r['externalPosition']=(proof.get('initialPositionEvidence',{}).get('positions') or [{}])[0]
    return records

def validate_trades(trades,start,end):
    if not isinstance(trades,list):raise ValueError('FILLS_SCHEMA')
    result=[];seen=set()
    for t in trades:
        if not isinstance(t,dict):raise ValueError('FILLS_SCHEMA')
        if not real_symbol(t.get('symbol')):continue
        ident=str(t['id'])
        if ident in seen:raise ValueError('DUPLICATE_FILL')
        seen.add(ident)
        if not start<=int(t['time'])<=end:raise ValueError('FILL_OUTSIDE_WINDOW')
        if t.get('positionSide') not in ('LONG','SHORT') or t.get('side') not in ('BUY','SELL'):raise ValueError('FILL_SIDE')
        if number(t['qty'])<=0 or number(t['price'])<=0:raise ValueError('FILL_SIZE')
        if abs(number(t['quoteQty'])-number(t['qty'])*number(t['price']))>D('.00000001'):raise ValueError('FILL_VALUE')
        number(t['realizedPnl']);number(t['commission'])
        result.append(t)
    return result

def is_open(t):
    return (t['positionSide']=='LONG')==(t['side']=='BUY')

def closed_rows(trades,positions,start,end,metadata=()):
    """Reconstruct flat-to-flat combined positions, backwards from current size.

    Partial exits of positions still open are excluded. Multi-fill and multiple
    closing orders within one cycle count once. No claim of full-cycle net when
    entry fills or earlier reductions fall outside this 24h interval.
    """
    positions=live_positions(positions);trades=validate_trades(trades,start,end)
    balances={};groups={}
    for p in positions:
        if p.get('separatedMode')!='COMBINED':raise ValueError('SEPARATED_HISTORY_UNSUPPORTED')
        key=(p['symbol'],p['side'])
        if key in balances:raise ValueError('AMBIGUOUS_POSITION_MODE')
        balances[key]=number(p['size'])
    for t in trades:groups.setdefault((t['symbol'],t['positionSide']),[]).append(t)
    closed=[];partial=D(0)
    for key,items in groups.items():
        balance=balances.get(key,D(0));cycle=[];is_closed=False
        def finish(full):
            nonlocal partial
            exits=[t for t in cycle if not is_open(t)]
            if not exits:return
            gross=sum((number(t['realizedPnl']) for t in exits),D(0))
            if not is_closed:partial+=gross;return
            q=sum((number(t['qty']) for t in exits),D(0))
            value=sum((number(t['quoteQty']) for t in exits),D(0))
            entries=[t for t in cycle if is_open(t)]
            fees=sum((number(t['commission']) for t in cycle),D(0)) if all(t.get('commissionAsset')=='USDT' for t in cycle) else None
            row={'symbol':key[0],'side':key[1],'closedAt':max(int(t['time']) for t in exits),
                 'quantity':str(q),'exit':str(value/q),'pnl':str(gross),'net':str(gross-fees) if full and fees is not None else None,
                 'fees':str(fees) if full and fees is not None else None,'leverage':None,'tp':['N/D: dato storico non disponibile'],
                 'entry':None,'fullCycle':full,'pnlScope':'ciclo completo' if full else 'realizzato nelle 24h',
                 'orderIds':sorted({str(t['orderId']) for t in exits})}
            if full and entries:
                row['entry']=str(sum((number(t['quoteQty']) for t in entries),D(0))/sum((number(t['qty']) for t in entries),D(0)))
            matched=[m for m in metadata if m['symbol']==key[0] and m['plan'].get('entry',{}).get('positionSide')==key[1]
                     and any(x in row['orderIds'] for x in m.get('exitIds',[str(m['detail'].get('exitOrderId'))]))
                     and len(row['orderIds'])==1 and number(m['detail'].get('quantity') or m.get('owned',{}).get('quantity',0))==q]
            if len(matched)==1:
                m=matched[0];o=m.get('owned') or {};detail=m['detail'];plan=m['plan']
                row['leverage']=plan.get('actualCrossLeverage') # actual verified setting at entry
                tp=m.get('externalOrder') or o.get('tpRequest',{})
                trigger=tp.get('stopPrice') if m.get('externalOrder') else tp.get('triggerPrice')
                if tp.get('type')=='TRAILING_MARKET':
                    row['tp']=[f"Trailing | attivazione {tp['activatePrice']} | rientro {number(tp['callbackRate'])*100:f}% | storico"]
                elif trigger is not None and m.get('state','CLOSED')=='CLOSED':
                    typ=tp.get('workingType') or tp.get('triggerPriceType')
                    row['tp']=[f"{number(trigger):f} | "+{'MARK_PRICE':'Mark','CONTRACT_PRICE':'Last'}.get(typ,'trigger N/D')+' | storico']
                entry=o.get('actualEntryCostUSDT') or detail.get('actualEntryCostUSDT')
                entryfee=o.get('actualEntryFeesUSDT') or detail.get('actualEntryFeesUSDT')
                if entry is not None:row['entry']=str(number(entry)/q)
                # Only use reconciled net if the exact exit value also matches.
                if number(detail.get('actualExitValueUSDT',-1))==value and entryfee is not None:
                    row['net']=str(number(detail['realizedNetBeforeFundingUSDT']))
                    row['fees']=str(number(entryfee)+number(detail['actualExitFeesUSDT']))
            closed.append(row)
        for t in sorted(items,key=lambda t:(int(t['time']),int(t['id'])),reverse=True):
            if not cycle:is_closed=balance==0 and not is_open(t)
            cycle.append(t)
            balance+=-number(t['qty']) if is_open(t) else number(t['qty'])
            if balance<0:raise ValueError('HISTORY_POSITION_MISMATCH')
            if balance==0:finish(True);cycle=[]
        if cycle:finish(False)
    return sorted(closed,key=lambda r:r['closedAt'],reverse=True),str(partial)

def fetch_history(read,start,end,*,limit_calls=15):
    """Time subdivision handles the API's 100-fill cap without dropping ties."""
    pending=[(start,end)];found={};calls=0
    while pending:
        lo,hi=pending.pop()
        if calls>=limit_calls:raise ValueError('HISTORY_TOO_LARGE')
        calls+=1;batch=read('/capi/v3/userTrades',startTime=lo,endTime=hi,limit=100)
        checked=validate_trades(batch,lo,hi)
        if len(batch)>=100:
            if lo==hi:raise ValueError('HISTORY_SATURATED_MILLISECOND')
            mid=(lo+hi)//2;pending.extend([(mid+1,hi),(lo,mid)]);continue
        for t in checked:
            if str(t['id']) in found:raise ValueError('DUPLICATE_FILL')
            found[str(t['id'])]=t
    return list(found.values())

def position_signature(positions):
    return sorted((str(p['id']),p['symbol'],p['side'],p['size'],p.get('updatedTime')) for p in live_positions(positions))

def collect(kind,root=ROOT,query=None,clock=time.time):
    from weex_api_budget import budget,BudgetDeferred
    if kind not in ('open','closed'):raise ValueError('REPORT_KIND')
    if query is None:
        from monitor import query
    started=clock();deadline=time.monotonic()+25
    initial=budget().used()
    if initial['pauseUntil']>clock():raise BudgetDeferred('REPORT_WAIT_API_BUDGET')
    def read(path,**params):
        if time.monotonic()>deadline:raise ValueError('REPORT_TIMEOUT')
        b=budget().used()
        if b['pauseUntil']>clock():raise BudgetDeferred('REPORT_WAIT_API_BUDGET')
        return query(path+('?' + urlencode(params) if params else ''))
    positions=read('/capi/v3/account/position/allPosition')
    live_positions(positions)
    end=int(clock()*1000)
    if kind=='open':
        algos=[];seen=set()
        for page in range(1,6):
            batch=read('/capi/v3/openAlgoOrders',page=page,limit=100)
            if not isinstance(batch,list):raise ValueError('ALGO_SCHEMA')
            for a in batch:
                ident=str(a['algoId'])
                if ident in seen:raise ValueError('REPEATED_ALGO_PAGE')
                seen.add(ident);algos.append(a)
            if len(batch)<100:break
        else:raise ValueError('ALGO_HISTORY_INCOMPLETE')
        trailing=[];seen_trailing=set()
        for page in range(5):
            batch=read('/capi/v3/trailing/openOrders',page=page,limit=100)
            if not isinstance(batch,list):raise ValueError('TRAILING_SCHEMA')
            for a in batch:
                ident=str(a['orderId'])
                if ident in seen_trailing:raise ValueError('REPEATED_TRAILING_PAGE')
                seen_trailing.add(ident);trailing.append(a)
            if len(batch)<100:break
        else:raise ValueError('TRAILING_HISTORY_INCOMPLETE')
        rows=open_rows(positions,algos,trailing,bot_tp_previews(root));partial='0'
    else:
        trades=fetch_history(read,end-DAY,end)
        after=read('/capi/v3/account/position/allPosition')
        if position_signature(positions)!=position_signature(after):raise ValueError('ACCOUNT_CHANGED_DURING_REPORT')
        rows,partial=closed_rows(trades,positions,end-DAY,end,journal_metadata(root))
        # Trade details do not include leverage or TP. Enrich missing TP only
        # from its exact executed order; do not mistake an exit price for a TP.
        for row in rows[:10]:
            if len(row['orderIds'])!=1 or not row['tp'][0].startswith('N/D'):continue
            try:
                order=read('/capi/v3/order',orderId=row['orderIds'][0])
                if (str(order.get('orderId'))!=row['orderIds'][0] or order.get('symbol')!=row['symbol']
                    or order.get('positionSide')!=row['side'] or order.get('status')!='FILLED'
                    or number(order.get('executedQty',-1))!=number(row['quantity'])):continue
                if order.get('type') in ('TAKE_PROFIT','TAKE_PROFIT_MARKET') and number(order.get('stopPrice',0))>0:
                    row['tp']=[f"{number(order['stopPrice']):f} | "+{'MARK_PRICE':'Mark','CONTRACT_PRICE':'Last'}.get(order.get('workingType'),'trigger N/D')+' | storico']
                else:row['tp']=['Uscita '+str(order.get('type','N/D'))+'; TP storico N/D']
            except Exception:
                # Already complete fills remain usable; missing metadata is N/D.
                break
    if clock()-started>30:raise ValueError('REPORT_TIMEOUT')
    return {'kind':kind,'observedAtMs':int(started*1000),'windowEndMs':end,'windowStartMs':end-DAY,
            'rows':rows,'partialRealized':partial,'stale':False,'error':None,'exchangeWrites':0}

def report(kind,root=ROOT):
    """Short cache prevents repeated menu taps consuming the trading API budget."""
    path=Path(root)/('telegram_positions_'+kind+'.json');old=None
    try:old=json.loads(path.read_text(encoding='utf-8'))
    except (OSError,ValueError):pass
    now_ms=int(time.time()*1000)
    if kind=='open':
        # Reuse the runner's account observation without relabeling its time.
        from weex_account_observation import load
        observed=load(root,max_age=86400)
        if observed and (not old or observed['startedAtMs']>old['observedAtMs']):
            try:
                old={'kind':'open','observedAtMs':observed['startedAtMs'],'windowEndMs':observed['completedAtMs'],
                     'rows':open_rows(observed['positions'],observed['conditionalOrders'],observed['trailingOrders'],bot_tp_previews(root)),
                     'partialRealized':'0','stale':False,'error':None,'exchangeWrites':0}
            except (ValueError,KeyError,TypeError,ArithmeticError):pass
    if old and 0<=now_ms-old['observedAtMs']<=30000:return {**old,'cached':True}
    try:
        result=collect(kind,root)
        tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(result),encoding='utf-8');os.replace(tmp,path)
        return result
    except Exception as exc:
        # Never expose signed URLs, credentials, request bodies or stack traces.
        reason='BUDGET API: riprova tra poco' if type(exc).__name__=='BudgetDeferred' else 'LETTURA NON COMPLETA: riprova'
        if old and 0<=now_ms-old['observedAtMs']<=DAY:return {**old,'stale':True,'error':reason}
        return {'kind':kind,'observedAtMs':None,'windowEndMs':now_ms,'windowStartMs':now_ms-DAY,
                'rows':[],'partialRealized':None,'stale':True,'error':reason,'exchangeWrites':0}
