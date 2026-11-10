"""Fresh account/market preflight for the persistent executor. GET requests only."""
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor
from weex_ai_universe import api_trading_symbols
from market_agents import analyze
from market_agents_rotating import apply_book_gate
from orderbook_liquidity import inspect
from weex_execution_readonly import pages
from weex_lifecycle import now
from weex_max_leverage import select as select_maximum_leverage


def context(gateway,item):
    from weex_simple_bot import public
    started=now();s=item['symbol'];p=item['plan'];read=gateway.read
    # Independent GET snapshots share the same capture window. Never serialize
    # network round trips until the first account snapshot is already stale.
    tasks={
        'market':lambda:analyze(s),'book':lambda:inspect(s),'allowed':api_trading_symbols,
        'metadata':lambda:public('/capi/v3/market/exchangeInfo',symbol=s),
        'brackets':lambda:public('/capi/v3/market/riskLimits',symbol=s),
        'positions':lambda:read('get_capi_v3_account_position_allPosition'),
        'orders':lambda:pages(read,'get_capi_v3_openOrders',identity='orderId',start=0),
        'algos':lambda:pages(read,'get_capi_v3_openAlgoOrders',identity='algoId',start=1),
        'account':lambda:read('get_capi_v3_account_accountConfig'),
        'balances':lambda:read('get_capi_v3_account_balance'),
        'config':lambda:read('get_capi_v3_account_symbolConfig',symbol=s),
        'fees':lambda:read('get_capi_v3_account_commissionRate',symbol=s)}
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures={k:pool.submit(fn) for k,fn in tasks.items()}
        data={k:f.result() for k,f in futures.items()}
    if not 0<=now()-started<=5000:raise ValueError('STALE_PREFLIGHT')
    allowed=s in data['allowed'];positions=data['positions'];orders=data['orders'];algos=data['algos']
    account=data['account'];balances=data['balances']
    config=next(x for x in data['config'] if x['symbol']==s)
    fees=data['fees']
    rate=next(fees[k] for k in ('apiTakerCommissionRate','apiTakerFeeRate','takerCommissionRate') if fees.get(k) is not None)
    market=apply_book_gate(data['market'],data['book']);book=market['realOrderBook']
    price=Decimal(book['bestAsk'] if p['entry']['side']=='BUY' else book['bestBid'])
    qty=Decimal(p['entry']['quantity']);leverage=Decimal(p['requestedLeverage']);notional=qty*price
    brackets=next(x['brackets'] for x in data['brackets'] if x['symbol']==s)
    metadata=next(x for x in data['metadata']['symbols'] if x['symbol']==s)
    import json
    from weex_simple_bot import R
    cfg=json.loads((R/'weex_ai_risk_config.json').read_text(encoding='utf-8'))
    budget = ({'cost_usdt':cfg['risk']['orderCostTargetUSDT'], 'entry_fee_rate':rate}
              if cfg['risk'].get('entryBudgetMode')=='COST_INCLUDING_ENTRY_FEE'
              else {'margin_usdt':cfg['risk']['initialMarginTargetUSDT']})
    maximum=select_maximum_leverage(metadata=metadata,brackets=brackets,
        reference_price=price,minimum=cfg['risk'].get('minimumLeverage',100),**budget)
    tier=any(Decimal(str(b['notionalFloor']))<=notional<Decimal(str(b['notionalCap']))
             and leverage<=Decimal(str(b['initialLeverage'])) for b in brackets)
    balance=next(x['availableBalance'] for x in balances if x['asset']=='USDT')
    if not isinstance(positions,list) or any(not isinstance(x,dict) or not x.get('symbol') for x in positions):
        raise ValueError('INVALID_POSITIONS')
    return {'observedAtMs':started,'complete':True,'apiEnabled':allowed,
            'accountCanTrade':account.get('canTrade'),'hedgeMode':account.get('dualSidePosition'),
            'depthUnitVerified':book.get('depthUnitVerified'),'liquidityPassed':book.get('passed'),
            'marketSignal':market.get('marketSignal'),'closedCandleTimes':market.get('closedCandleTimes'),
            'riskTierVerified':tier,'availableBalance':balance,
            'maximumPermittedLeverage':maximum['leverage'],
            'positions':positions,'openOrders':orders,'conditionalOrders':algos,'symbolConfig':config,
            'referencePrice':str(price),'exitFeeRate':str(rate)}


def step(trade_id,*,authorize_request=None):
    """No authorizer is supplied by the scheduled runner; default still cannot write."""
    import json
    from weex_simple_bot import make_client,R
    from weex_lifecycle import Lifecycle,SDKGateway
    gateway=SDKGateway(make_client(write_authorizer=authorize_request))
    engine=Lifecycle(R/'weex_lifecycle.sqlite3',gateway,
                     lambda:json.loads((R/'weex_ai_risk_config.json').read_text(encoding='utf-8')))
    return engine.advance(trade_id,lambda symbol:context(gateway,engine.get(trade_id)))
