"""Compare current symbol margin/leverage with the requested strategy; GET only."""
import json
from concurrent.futures import ThreadPoolExecutor
from collections import Counter
from datetime import datetime,timezone
from decimal import Decimal
from pathlib import Path
from weex_max_leverage import select as select_maximum_leverage


def indexed(rows):
    if not isinstance(rows,list):raise ValueError('INVALID_LIST')
    result={}
    for row in rows:
        if not isinstance(row,dict) or not row.get('symbol') or row['symbol'] in result:
            raise ValueError('INVALID_OR_DUPLICATE_SYMBOL')
        result[row['symbol']]=row
    return result


def assess(metadata,allowed,configs,tiers,margin,prices=None):
    """Public tier limits validate a scenario, not acceptance of a leverage write."""
    meta=indexed(metadata);conf=indexed(configs);brackets=indexed(tiers)
    margin=Decimal(str(margin))
    if not margin.is_finite() or margin<=0:raise ValueError('INVALID_MARGIN')
    results=[]
    for symbol,m in sorted(meta.items()):
        maximum=Decimal(str(m['maxLeverage']))
        if (symbol not in allowed or m.get('contractType')!='PERPETUAL' or m.get('quoteAsset')!='USDT'
                or maximum<75):continue
        row={'symbol':symbol,'requestedLeverage':str(maximum),'marginTargetUSDT':str(margin)}
        selected=None
        if prices is not None:
            try:
                selected=select_maximum_leverage(metadata=m,brackets=brackets.get(symbol,{}).get('brackets'),
                                                margin_usdt=margin,reference_price=prices[symbol])
                maximum=Decimal(selected['leverage'])
                row.update(requestedLeverage=str(maximum),sizing=selected)
            except (ValueError,KeyError) as exc:
                row.update(state='NO_VALID_LEVERAGE_OR_SIZE',matches=False,reason=str(exc));results.append(row);continue
        c=conf.get(symbol)
        if c is None:
            row.update(state='ACCOUNT_CONFIG_MISSING',matches=False)
        else:
            actual=Decimal(str(c['crossLeverage']))
            if not actual.is_finite() or actual<=0:raise ValueError('INVALID_ACCOUNT_LEVERAGE')
            notional=Decimal(selected['notionalUSDT']) if selected else margin*maximum
            valid=False
            for b in brackets.get(symbol,{}).get('brackets',[]):
                floor,cap,lev=(Decimal(str(b[k])) for k in ('notionalFloor','notionalCap','initialLeverage'))
                if any(not x.is_finite() for x in (floor,cap,lev)) or floor<0 or cap<=floor or lev<=0:
                    raise ValueError('INVALID_BRACKET')
                if floor<=notional<cap and maximum<=lev:valid=True
            matches=c.get('marginType')=='CROSSED' and actual==maximum and valid
            row.update(currentMarginType=c.get('marginType'),currentCrossLeverage=str(actual),
                publicTierAllowsTarget=valid,scenarioNotionalUSDT=str(notional),matches=matches,
                state='MATCHES' if matches else 'PUBLIC_TIER_UNCONFIRMED' if not valid else 'SETUP_REQUIRED',
                requiredChanges=([{'field':'marginType','desired':'CROSSED'}] if c.get('marginType')!='CROSSED' else [])+
                                ([{'field':'crossLeverage','desired':str(maximum)}] if actual!=maximum else []))
        results.append(row)
    if not results:raise ValueError('EMPTY_UNIVERSE')
    return results


def run(root=None):
    from weex_simple_bot import make_client,read,public,R
    from weex_ai_universe import api_trading_symbols
    root=Path(root) if root else R
    cfg=json.loads((root/'weex_ai_risk_config.json').read_text(encoding='utf-8'))
    client=make_client()
    metadata=public('/capi/v3/market/exchangeInfo')['symbols']
    allowed=api_trading_symbols()
    configs=read(client,'get_capi_v3_account_symbolConfig')
    # The bulk response may contain only explicitly configured symbols. Ask each missing
    # eligible symbol separately instead of treating absence as an unknown account setting.
    present=indexed(configs)
    missing=[m['symbol'] for m in metadata if m['symbol'] in allowed and m.get('contractType')=='PERPETUAL'
             and m.get('quoteAsset')=='USDT' and Decimal(str(m['maxLeverage']))>=75 and m['symbol'] not in present]
    def fetch(symbol):
        try:
            rows=read(make_client(),'get_capi_v3_account_symbolConfig',symbol=symbol)
            row=indexed(rows).get(symbol)
            return symbol,row,None if row else 'NOT_RETURNED'
        except Exception as exc:return symbol,None,type(exc).__name__
    errors={}
    with ThreadPoolExecutor(max_workers=3) as pool:
        for symbol,row,error in pool.map(fetch,missing):
            if row:configs.append(row)
            else:errors[symbol]=error
    tiers=public('/capi/v3/market/riskLimits')
    prices={s:r['askPrice'] for s,r in indexed(public('/capi/v3/market/ticker/bookTicker')).items()}
    account=read(client,'get_capi_v3_account_accountConfig')
    rows=assess(metadata,allowed,configs,tiers,cfg['risk']['initialMarginTargetUSDT'],prices=prices)
    report={'checkedAt':datetime.now(timezone.utc).isoformat(),'mode':'READ_ONLY',
            'accountCanTrade':account.get('canTrade'),'hedgeMode':account.get('dualSidePosition'),
            'symbols':len(rows),'counts':dict(Counter(x['state'] for x in rows)),
            'allConfigured':all(x['matches'] for x in rows),'results':rows,
            'perSymbolFallbackQueries':len(missing),'readErrors':errors,
            'settingsChanged':False,'ordersSubmitted':False,
            'leveragePolicy':'MAXIMUM_LEVERAGE_FIRST_MINIMUM_100',
            'note':'Maximum permitted leverage >=100 with quantity capped to margin and tier limits. Exchange acceptance still requires setting and fresh readback before a future authorized entry.'}
    path=root/'weex_account_setup_audit_latest.json';tmp=path.with_suffix('.tmp')
    tmp.write_text(json.dumps(report,indent=2),encoding='utf-8');tmp.replace(path)
    return report

if __name__=='__main__':
    report=run()
    print(json.dumps({k:report[k] for k in ('checkedAt','symbols','counts','settingsChanged','ordersSubmitted')}))
