"""Conservative proof for a fully externally closed, isolated bot position."""
import hashlib,json
from decimal import Decimal as D

def number(x):
    n=D(str(x))
    if not n.is_finite():raise ValueError('NONFINITE')
    return n

def fills(order,rows):
    if not isinstance(rows,list) or not 0<len(rows)<100:raise ValueError('INCOMPLETE_FILLS')
    seen=set();qty=value=fees=D(0)
    for f in rows:
        if (not f.get('id') or str(f['id']) in seen or str(f.get('orderId'))!=str(order['orderId'])
            or any(f.get(k)!=order[k] for k in ('symbol','side','positionSide'))
            or int(f['time'])<int(order['time']) or f.get('commissionAsset')!='USDT'):
            raise ValueError('FILL_BINDING')
        seen.add(str(f['id']));q=number(f['qty']);p=number(f['price']);fee=number(f['commission'])
        if q<=0 or p<=0 or fee<0 or number(f['quoteQty'])!=q*p:raise ValueError('FILL_ECONOMICS')
        qty+=q;value+=q*p;fees+=fee
    if qty!=number(order['executedQty']):raise ValueError('INCOMPLETE_QUANTITY')
    # WEEX sometimes reports last-fill price * full quantity as cumQuote.
    # Accept that observed format only with a complete, bound fill set.
    if number(order['cumQuote'])!=value and not (
        len({number(f['price']) for f in rows})>1
        and number(order['avgPrice']) in {number(f['price']) for f in rows}
        and number(order['cumQuote'])==qty*number(order['avgPrice'])):
        raise ValueError('ORDER_VALUE_MISMATCH')
    return qty,value,fees

def prove(item,orders,by_order,bot_exit_ids=()):
    owned=item['owned'];plan=item['plan'];symbol=item['symbol'];entry=plan['entry']
    if not isinstance(plan.get('beforePositions'),list) or any(p.get('symbol')==symbol for p in plan['beforePositions']):
        raise ValueError('PREEXISTING_EXPOSURE')
    if not owned.get('positionId'):raise ValueError('OWNERSHIP_PROOF_MISSING')
    if not isinstance(orders,list) or len({str(o['orderId']) for o in orders})!=len(orders):raise ValueError('AMBIGUOUS_HISTORY')
    matches=[o for o in orders if str(o['orderId'])==owned['entryOrderId']]
    if len(matches)!=1:raise ValueError('ENTRY_NOT_FOUND')
    opened=matches[0]
    if (opened.get('clientOrderId')!=item['id'] or opened.get('reduceOnly') is not False
        or opened.get('status')!='FILLED' or opened.get('type')!='MARKET'
        or any(opened.get(k)!=entry[k] for k in ('symbol','side','positionSide'))):
        raise ValueError('ENTRY_BINDING')
    q,cost,fee=fills(opened,by_order[str(opened['orderId'])])
    if (q!=number(owned['quantity']) or cost!=number(owned['actualEntryCostUSDT'])
        or fee!=number(owned['actualEntryFeesUSDT'])):raise ValueError('ENTRY_CHANGED')
    closed=value=exit_fee=D(0);exits=[]
    for o in orders:
        if o is opened:continue
        if o['symbol']!=symbol or int(o['time'])<int(opened['time']):raise ValueError('HISTORY_SCOPE')
        if number(o['executedQty'])==0 and o['status'] in ('CANCELED','EXPIRED','REJECTED'):continue
        if (o.get('status')!='FILLED' or o.get('reduceOnly') is not True
            or o.get('positionSide')!=entry['positionSide']
            or o.get('side')!=('SELL' if entry['side']=='BUY' else 'BUY')
            or (str(o['orderId']) not in bot_exit_ids and (o.get('type') not in ('MARKET','LIMIT')
                or o.get('clientOrderId')==plan['tpClientId']))):raise ValueError('UNRELATED_OR_PARTIAL_ORDER')
        qty,v,f=fills(o,by_order[str(o['orderId'])]);closed+=qty;value+=v;exit_fee+=f;exits.append(str(o['orderId']))
    if closed!=q:raise ValueError('CLOSE_QUANTITY_MISMATCH')
    net=(value-cost if entry['side']=='BUY' else cost-value)-fee-exit_fee
    digest=hashlib.sha256(json.dumps({'orders':orders,'fills':by_order},sort_keys=True).encode()).hexdigest()
    used_bot_tp=bool(set(exits)&set(bot_exit_ids))
    return {'resolution':'CLOSED_BOT_TP_VERIFIED' if used_bot_tp else 'CLOSED_EXTERNAL_WEEX_HISTORY',
        'externalMarketClose':not used_bot_tp,'botTPUsed':used_bot_tp,
        'entryOrderId':owned['entryOrderId'],'exitOrderIds':exits,'quantity':str(q),
        'actualExitValueUSDT':str(value),'actualExitFeesUSDT':str(exit_fee),
        'realizedNetBeforeFundingUSDT':str(net),'fundingIncluded':False,
        'targetMetBeforeFunding':net>=number(plan['targetNetProfitUSDT']),
        'evidenceSha256':digest}

def flat_and_orphan(item,rows,ack_id):
    positions,orders,algos=rows;symbol=item['symbol'];tp=item['owned']['tpRequest']
    if any(not isinstance(g,list) or any(not isinstance(x,dict) or not x.get('symbol') for x in g) for g in rows):
        raise ValueError('ACCOUNT_SCHEMA')
    if any(p['symbol']==symbol for p in positions):raise ValueError('POSITION_PRESENT')
    if any(o['symbol']==symbol for o in orders):raise ValueError('REGULAR_ORDER_PRESENT')
    relevant=[a for a in algos if a['symbol']==symbol]
    if not relevant:return None
    if len(relevant)!=1:raise ValueError('OTHER_CONDITIONAL_ORDER')
    a=relevant[0]
    if str(a.get('algoId'))!=str(ack_id) or a.get('algoStatus') not in ('NEW','UNTRIGGERED'):
        raise ValueError('ORPHAN_NOT_EXACT_OWNED_TP')
    if not tp_parameters_match(item,a):raise ValueError('ORPHAN_NOT_EXACT_OWNED_TP')
    return a

def tp_parameters_match(item,a):
    tp=item['owned']['tpRequest'];symbol=item['symbol']
    from weex_trailing import matches_request,is_trailing
    if is_trailing(item['plan']):valid=matches_request(a,tp)
    else:
        valid=(a.get('clientAlgoId')==tp['clientAlgoId'] and a.get('symbol')==symbol
            and a.get('positionSide')==tp['positionSide']
            and a.get('side')==('SELL' if tp['positionSide']=='LONG' else 'BUY')
            and a.get('orderType')=='TAKE_PROFIT_MARKET' and a.get('reduceOnly') is True
            and a.get('closePosition')==tp.get('closePosition')
            and a.get('workingType')==tp['triggerPriceType']
            and number(a['quantity'])==number(tp['quantity'])
            and number(a['triggerPrice'])==number(tp['triggerPrice']))
    return valid

def verify_bot_exit(item,algo,order,ack_id):
    """Bind a filled order to the exact TP acknowledgement and immutable plan."""
    if (str(algo.get('algoId'))!=str(ack_id) or algo.get('algoStatus') not in ('FILLED','TRIGGERED')
        or not tp_parameters_match(item,algo)):raise ValueError('BOT_TP_HISTORY_MISMATCH')
    expected=str(algo.get('actualOrderId') or algo['algoId']);tp=item['owned']['tpRequest']
    if (str(order.get('orderId'))!=expected or order.get('symbol')!=item['symbol']
        or order.get('side')!=algo['side'] or order.get('positionSide')!=tp['positionSide']
        or order.get('reduceOnly') is not True or order.get('status')!='FILLED'
        or not 0<number(order['executedQty'])<=number(item['owned']['quantity'])):
        raise ValueError('BOT_TP_EXIT_BINDING')
    if not algo.get('actualOrderId'):
        from weex_trailing import is_trailing,TYPES
        types=TYPES if is_trailing(item['plan']) else ('TAKE_PROFIT_MARKET',)
        if order.get('clientOrderId')!=tp['clientAlgoId'] or order.get('type') not in types:
            raise ValueError('BOT_TP_CLIENT_BINDING')
    return expected
