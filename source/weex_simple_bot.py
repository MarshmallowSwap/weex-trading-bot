from weex_api_budget import open_url
"""One read-only WEEX runner: scan, account checks, sizing and order preview.

No order submission, leverage changes or Telegram messages. Strategy previews
maximize permitted leverage with a floor of 75x. The old 1x pilot is disabled.
"""
import argparse
import hashlib
import json
import sqlite3
import urllib.parse
import urllib.request
from contextlib import closing
from datetime import datetime, timezone
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
from pathlib import Path

from market_agents import analyze
from market_agents_rotating import apply_book_gate, run as scan
from orderbook_liquidity import inspect
from weex_margin_sizing import size_for_contract
from weex_max_leverage import select as select_maximum_leverage
from weex_ai_universe import api_trading_symbols
from weex_persistent_execution import Journal
from weex_execution_readonly import pages, recover
from weex_http_guard import HttpReadOnlySession, ScopedTradingSession, prepare_sdk_order, prepare_sdk_request
from weex_lifecycle import Lifecycle,SDKGateway
from weex_capacity import account_capacity, lifecycle_position_ids

R = Path(__file__).resolve().parent
DB = R / 'weex_simple_bot.sqlite3'


def decide(market, positions, orders, cfg, managed_position_ids=None):
    reasons = []
    symbol = market.get('symbol', 'ETHUSDT')
    signal = market.get('marketSignal', market.get('decision'))
    if signal not in ('LONG', 'SHORT'):
        reasons.append('NO_CONFIRMED_SIGNAL')
    if market.get('momentum', {}).get('confirmed') is not True:
        reasons.append('MOMENTUM_NOT_CONFIRMED')
    liquidity = market.get('liquidity', {})
    book = market.get('realOrderBook', {})
    if (liquidity.get('proxyOnly') is not False or liquidity.get('passed') is not True
            or book.get('passed') is not True or book.get('depthUnitVerified') is not True):
        reasons.append('REAL_ORDERBOOK_NOT_CERTIFIED')
    valid_account = isinstance(positions, list) and isinstance(orders, list)
    if valid_account:
        valid_account = all(isinstance(x, dict) and isinstance(x.get('symbol'), str)
                            and x['symbol'] for x in positions + orders)
    if not valid_account:
        reasons.append('ACCOUNT_READ_FAILED')
    else:
        if any(x['symbol'] == symbol for x in positions + orders):
            reasons.append('SYMBOL_OCCUPIED')
        cap = cfg.get('telegramSettings', {}).get('maxConcurrentPositions', {}).get('default', 2)
        # Count exposure and possible entries, excluding verified full closing TPs.
        capacity = account_capacity(positions, orders, managed_position_ids=managed_position_ids)
        if (type(cap) is not int or not 1 <= cap <= 10 or capacity["count"] >= cap):
            reasons.append('POSITION_LIMIT_REACHED')
    if cfg.get('execution', {}).get('enabled') is not True:
        reasons.append('LIVE_EXECUTION_OFF')
    if (cfg.get('risk', {}).get('stopLoss', {}).get('enabled') is False
            and cfg.get('execution', {}).get('allowOrdersWithoutStop') is not True):
        reasons.append('ORDERS_WITHOUT_STOP_NOT_AUTHORIZED')
    return {'decision': 'WAIT' if reasons else 'SIGNAL_REQUIRES_EXECUTOR',
            'signal': signal, 'reasons': reasons, 'ordersSubmitted': False}


def public(path, **params):
    url = 'https://api-contract.weex.com' + path + '?' + urllib.parse.urlencode(params)
    with open_url(url, timeout=12) as response:
        return json.load(response)


def make_client(*,write_authorizer=None):
    import official_weex_live_sdk_adapter  # establishes vendored SDK paths
    from weex_common.configuration import ConfigurationRestAPI
    from weex_contract_sdk import Contract
    cred = json.loads((R / 'weex_credentials.json').read_text(encoding='utf-8'))
    return Contract(config_rest_api=ConfigurationRestAPI(
        base_path='https://api-contract.weex.com', api_key=cred['api_key'],
        api_secret=cred['secret_key'], passphrase=cred['passphrase'], timeout=12, max_retries=0,
        session=HttpReadOnlySession() if write_authorizer is None else ScopedTradingSession(
            lambda:json.loads((R/'weex_ai_risk_config.json').read_text(encoding='utf-8')),write_authorizer)))


def read(client, operation, **query):
    from weex_contract_sdk.rest_api.operations import OPERATIONS
    if OPERATIONS.get(operation, {}).get('method') != 'GET':
        raise PermissionError('GET_ONLY_RUNNER')
    response = client.rest_api.execute_operation(operation, {'query': query})
    if response.status_code != 200:
        raise ValueError('ACCOUNT_HTTP_ERROR')
    return response.data


def open_orders(client):
    result, seen = [], set()
    for page in range(100):
        batch = read(client, 'get_capi_v3_openOrders', page=page, limit=100)
        if not isinstance(batch, list):
            raise ValueError('INVALID_ORDERS_RESPONSE')
        for row in batch:
            if not isinstance(row, dict) or not row.get('symbol') or not row.get('orderId'):
                raise ValueError('INVALID_ORDER')
            identity = str(row['orderId'])
            if identity in seen:
                raise ValueError('ORDERS_PAGINATION_REPEATED')
            seen.add(identity)
            result.append(row)
        if len(batch) < 100:
            return result
    raise ValueError('ORDERS_PAGINATION_INCOMPLETE')


def preview(market, metadata, symbol_config, cfg, *, pilot=False, commission=None, brackets=None, available_balance=None, manual_override=False):
    """A numerical scenario; its presence does not authorize submission."""
    side = market.get('marketSignal', market.get('decision'))
    if side not in ('LONG', 'SHORT'):
        return {'status': 'WAIT_NO_SIGNAL'}
    symbol = market['symbol']
    if metadata.get('symbol') != symbol or symbol_config.get('symbol') != symbol:
        raise ValueError('SYMBOL_METADATA_MISMATCH')
    if pilot and symbol != 'ETHUSDT':
        raise ValueError('PILOT_ONLY_ETHUSDT')
    margin = '5' if pilot else cfg['risk']['initialMarginTargetUSDT']
    leverage = Decimal('1') if pilot else Decimal(str(metadata['maxLeverage']))
    actual = Decimal(str(symbol_config['crossLeverage']))
    if not actual.is_finite() or actual <= 0:
        raise ValueError('INVALID_ACCOUNT_LEVERAGE')
    book = market['realOrderBook']
    price = Decimal(book['bestAsk'] if side == 'LONG' else book['bestBid'])
    if commission is not None and commission.get('symbol') != symbol:
        raise ValueError('COMMISSION_SYMBOL_MISMATCH')
    fee_data = commission if commission is not None else metadata
    fee_fallback = 'takerCommissionRate' if commission is not None else 'takerFeeRate'
    fee_value=next((fee_data[k] for k in ('apiTakerCommissionRate','apiTakerFeeRate',fee_fallback) if fee_data.get(k) is not None),None)
    fee = Decimal(str(fee_value))
    if not fee.is_finite() or not 0 <= fee < 1:
        raise ValueError('INVALID_ENTRY_FEE')
    cost_mode = cfg['risk'].get('entryBudgetMode') == 'COST_INCLUDING_ENTRY_FEE'
    if cost_mode and (pilot or commission is None or brackets is None):
        raise ValueError('COST_REQUIRES_ACCOUNT_FEE_AND_LEVERAGE_TIERS')
    if not pilot and leverage<100:raise ValueError('LEVERAGE_BELOW_100')
    if not pilot and brackets is not None:
        budget_args = ({'cost_usdt': cfg['risk']['orderCostTargetUSDT'], 'entry_fee_rate': fee}
                       if cost_mode else {'margin_usdt': margin})
        sizing=select_maximum_leverage(metadata=metadata,brackets=brackets,**budget_args,
                                      reference_price=price,minimum=cfg['risk'].get('minimumLeverage',100))
        leverage=Decimal(sizing['leverage'])
    else:
        # Unverified legacy calculation only; absent tiers always block submission below.
        sizing = size_for_contract(metadata=metadata, margin_usdt=margin,
                                   leverage=leverage, reference_price=price)
    qty, tick = Decimal(sizing['quantity']), Decimal(sizing['priceTick'])
    target = Decimal('0.5') if pilot else Decimal(str(cfg['strategySettings']['targetNetProfitUSDT']))
    if not fee.is_finite() or not 0 <= fee < 1 or not target.is_finite() or target <= 0:
        raise ValueError('INVALID_FEE_OR_PROFIT')
    # NET is the legacy behavior. For GROSS_BEFORE_COSTS the TP trigger
    # targets raw price PnL only; fees/slippage/funding reduce realized PnL.
    accounting = cfg['strategySettings'].get('tpAccountingMode','NET')
    if accounting not in ('NET','GROSS_BEFORE_COSTS'):
        raise ValueError('TP_ACCOUNTING_MODE_INVALID')
    if side == 'LONG':
        tp = (price + target / qty if accounting=='GROSS_BEFORE_COSTS'
              else (price * (1 + fee) + target / qty) / (1 - fee))
        rounding = ROUND_CEILING
    else:
        tp = (price - target / qty if accounting=='GROSS_BEFORE_COSTS'
              else (price * (1 - fee) - target / qty) / (1 + fee))
        rounding = ROUND_FLOOR
    tp = (tp / tick).to_integral_value(rounding=rounding) * tick
    if tp <= 0:
        raise ValueError('UNREACHABLE_PROFIT_TARGET')
    identity = hashlib.sha256(json.dumps([symbol, side, market.get('closedCandleTimes'), market.get('timeframes'), pilot], sort_keys=True).encode()).hexdigest()[:24]
    blockers = ['STOP_BEFORE_SUBMISSION']
    if not manual_override and book.get('depthUnitVerified') is not True:
        blockers.append('DEPTH_UNITS_UNVERIFIED')
    if not manual_override and book.get('passed') is not True:
        blockers.append('LIQUIDITY_CHECK_FAILED')
    if symbol_config.get('marginType') != 'CROSSED':
        blockers.append('CROSS_MODE_NOT_SET')
    if actual != leverage:
        blockers.append('LEVERAGE_CHANGE_REQUIRED')
    tier_verified = False
    if brackets is not None:
        notional = Decimal(sizing['notionalUSDT'])
        for row in brackets:
            floor, cap, maximum = (Decimal(str(row[k])) for k in ('notionalFloor','notionalCap','initialLeverage'))
            if any(not n.is_finite() for n in (floor,cap,maximum)) or floor<0 or cap<=floor or maximum<=0:
                raise ValueError('INVALID_RISK_BRACKET')
            if floor <= notional < cap and leverage <= maximum:
                tier_verified = True
    if not tier_verified:
        blockers.append('PUBLIC_LEVERAGE_TIER_NOT_VERIFIED')
    if actual != leverage:
        blockers.append('REQUESTED_LEVERAGE_NOT_CONFIRMED_ON_ACCOUNT')
    required = Decimal(sizing['initialMarginUSDT']) + qty*price*fee
    balance_ok = None
    if available_balance is not None:
        available = Decimal(str(available_balance))
        if not available.is_finite() or available < 0:
            raise ValueError('INVALID_AVAILABLE_BALANCE')
        balance_ok = available >= required
    if balance_ok is not True:
        blockers.append('INSUFFICIENT_OR_UNVERIFIED_AVAILABLE_BALANCE')
    if commission is None:
        blockers.append('ACCOUNT_COMMISSION_NOT_VERIFIED')
    return {'status': 'BLOCKED_PREVIEW', 'mode': 'STRATEGY_COST' if cost_mode else ('PILOT_1X_MAX_5_NOTIONAL' if pilot else 'STRATEGY_MARGIN'),
            'sizing': sizing, 'actualCrossLeverage': str(actual), 'requestedLeverage': str(leverage),
            'estimatedEntryFeeUSDT': str(qty * price * fee), 'targetNetProfitUSDT': str(target),
            'exitFeeRate':str(fee),
            'feeRateSource': 'authenticated_account' if commission is not None else 'exchangeInfo_estimate',
            'publicRiskTierVerified': tier_verified, 'balanceCoversMarginAndEntryFee': balance_ok,
            'requiredMarginAndEntryFeeUSDT': str(required), 'fundingAndSlippageIncluded': False,
            'manualSignalOverride': bool(manual_override),
            'blockers': blockers, 'orderPreview': {
                'symbol': symbol, 'side': 'BUY' if side == 'LONG' else 'SELL', 'positionSide': side,
                'type': 'MARKET', 'quantity': format(qty,'f'), 'newClientOrderId': 'wxpreview_' + identity,
                'tpTriggerPrice': format(tp,'f'), 'TpWorkingType': 'MARK_PRICE'}}


def run(symbol=None, *, pilot=False, diagnostics_only=False):
    cfg = json.loads((R / 'weex_ai_risk_config.json').read_text(encoding='utf-8'))
    if pilot:raise ValueError('PILOT_1X_DISABLED_MINIMUM_LEVERAGE_75')
    if diagnostics_only:
        if symbol:raise ValueError('DIAGNOSTICS_EXPECT_FULL_SCANNER')
        from weex_local_diagnostics import publish
        return publish(R,cfg,scan,decide)
    if pilot and symbol != 'ETHUSDT':
        raise ValueError('USE_PILOT_WITH_ETHUSDT')
    if symbol and symbol not in api_trading_symbols():
        raise ValueError('SYMBOL_NOT_API_ENABLED')
    scan_report = None if symbol else scan()
    markets = [apply_book_gate(analyze(symbol), inspect(symbol))] if symbol else scan_report['results']
    market_source_at = datetime.now(timezone.utc).isoformat() if symbol else scan_report['asOf']
    client = make_client()
    positions = read(client, 'get_capi_v3_account_position_allPosition')
    orders = open_orders(client)
    conditional_orders = pages(lambda operation, **query: read(client, operation, **query),
                              'get_capi_v3_openAlgoOrders', identity='algoId', start=1)
    account = read(client, 'get_capi_v3_account_accountConfig')
    balances = read(client, 'get_capi_v3_account_balance')
    available = next((row['availableBalance'] for row in balances if row.get('asset') == 'USDT'), None)
    if not isinstance(positions, list) or not isinstance(account, dict):
        raise ValueError('INVALID_ACCOUNT_RESPONSE')
    results = []
    owned_ids=lifecycle_position_ids(R / 'weex_user_live_lifecycle.sqlite3')
    for market in markets:
        decision = decide(market, positions, orders + conditional_orders, cfg, managed_position_ids=owned_ids)
        if account.get('canTrade') is not True:
            decision['reasons'].append('ACCOUNT_TRADING_DISABLED')
            decision['decision'] = 'WAIT'
        item = {'symbol': market['symbol'], 'marketSignal': market.get('marketSignal', market.get('decision')),
                **decision, 'realOrderBook': market.get('realOrderBook'),
                'momentum':market.get('momentum'), 'closedCandleTimes':market.get('closedCandleTimes'),
                'observedAt':market.get('observedAt')}
        blocked_account = any(r in decision['reasons'] for r in ('SYMBOL_OCCUPIED', 'ACCOUNT_READ_FAILED', 'POSITION_LIMIT_REACHED', 'ACCOUNT_TRADING_DISABLED'))
        if (item['marketSignal'] in ('LONG', 'SHORT') and not blocked_account
                and market.get('realOrderBook',{}).get('passed') is True):
            try:
                info = public('/capi/v3/market/exchangeInfo', symbol=market['symbol'])['symbols']
                config = read(client, 'get_capi_v3_account_symbolConfig', symbol=market['symbol'])
                metadata = next(x for x in info if x['symbol'] == market['symbol'])
                current = next(x for x in config if x['symbol'] == market['symbol'])
                commission = read(client, 'get_capi_v3_account_commissionRate', symbol=market['symbol'])
                tiers = public('/capi/v3/market/riskLimits', symbol=market['symbol'])
                brackets = next(x['brackets'] for x in tiers if x['symbol'] == market['symbol'])
                item['plan'] = preview(market, metadata, current, cfg, pilot=pilot,
                                       commission=commission, brackets=brackets, available_balance=available)
            except ValueError as exc:
                item['plan'] = {'status': 'BLOCKED_RULES', 'reason': str(exc)}
            except Exception as exc:
                item['plan'] = {'status': 'ERROR', 'error': type(exc).__name__}
        results.append(item)
    now = datetime.now(timezone.utc).isoformat()
    journal = Journal(R / 'weex_execution_journal.sqlite3')
    lifecycle=Lifecycle(R/'weex_lifecycle.sqlite3',SDKGateway(client),
                        lambda:json.loads((R/'weex_ai_risk_config.json').read_text(encoding='utf-8')))
    recovery = recover(journal, lambda operation, **query: read(client, operation, **query), orders)
    baseline = [{k: p.get(k) for k in ('id', 'symbol', 'side', 'size')} for p in positions]
    for item in results:
        plan = item.get('plan', {})
        if (plan.get('status') == 'BLOCKED_PREVIEW'
                and (item.get('realOrderBook') or {}).get('passed') is True
                and (item.get('realOrderBook') or {}).get('depthUnitVerified') is True):
            try:
                intent = journal.prepare(plan['orderPreview']['newClientOrderId'],
                    plan['orderPreview'], baseline, plan['blockers'] + item['reasons'])
                plan['orderPreview'] = intent['payload']
                item['sdkPreflight'] = prepare_sdk_order(intent['payload'])
                item['persistentIntent'] = {'clientOrderId': intent['client_id'], 'state': intent['state'],
                                          'canSubmit': False, 'canClose': False}
                fullplan={**plan,'beforePositions':baseline,'closedCandleTimes':item.get('closedCandleTimes')}
                trade=lifecycle.prepare(intent['client_id'],fullplan)
                # Never call advance from the scheduled diagnostic runner: production remains pretrade.
                item['lifecycle']={'tradeId':trade['id'],'state':trade['state'],'ordersSubmitted':False,
                    'entry':trade['plan']['entry'],'tpClientId':trade['plan']['tpClientId'],
                    'setupRequests':trade['plan']['setupRequests'],
                    'entrySdkCheck':prepare_sdk_request('post_capi_v3_order',trade['plan']['entry']),
                    'tpPolicy':'DEDICATED_REDUCE_ONLY_AFTER_CONFIRMED_FILL'}
            except ValueError as exc:
                item['persistentIntent'] = {'state': 'BLOCKED', 'reason': str(exc), 'canSubmit': False}
    with closing(sqlite3.connect(DB)) as db, db:
        db.execute('CREATE TABLE IF NOT EXISTS decisions (id INTEGER PRIMARY KEY AUTOINCREMENT,ts TEXT NOT NULL,symbol TEXT NOT NULL,signal TEXT,decision TEXT NOT NULL,reasons TEXT NOT NULL)')
        for item in results:
            db.execute('INSERT INTO decisions(ts,symbol,signal,decision,reasons) VALUES(?,?,?,?,?)',
                       (now, item['symbol'], item['marketSignal'], item['decision'], json.dumps(item['reasons'])))
    report = {'checkedAt': now, 'sourceMarketAt':market_source_at, 'mode': 'READ_ONLY_PREVIEW', 'positionCount': len(positions),
              'openOrderCount': len(orders), 'accountCanTrade': account.get('canTrade'),
              'conditionalOrderCount': len(conditional_orders), 'executionJournal': journal.overview(),
              'restartRecovery': recovery,
              'lifecycle':{'mode':'PRETRADE','states':lifecycle.states(),'liveWritesEnabled':False},
              'results': results, 'ordersSubmitted': False}
    target = R / 'weex_simple_bot_latest.json'
    tmp = target.with_suffix('.tmp')
    tmp.write_text(json.dumps(report, indent=2), encoding='utf-8')
    tmp.replace(target)
    return report


def summary(report):
    results = report['results']
    return {'checkedAt':report['checkedAt'], 'mode':report['mode'], 'symbols':len(results),
            'marketSignals':sum(x.get('marketSignal') in ('LONG','SHORT') for x in results),
            'preparedPlans':sum(x.get('plan',{}).get('status')=='BLOCKED_PREVIEW' for x in results),
            'errors':sum(x.get('marketSignal')=='ERROR' or x.get('plan',{}).get('status')=='ERROR'
                         or x.get('persistentIntent',{}).get('state')=='BLOCKED' for x in results),
            'journalIntents':report.get('executionJournal',{}).get('total'),
            'recoveryObservations':len(report.get('restartRecovery',{}).get('observations',[])),
            'conditionalOrderCount':report.get('conditionalOrderCount'),
            'positionCount':report['positionCount'], 'openOrderCount':report['openOrderCount'],
            'ordersSubmitted':False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--symbol')
    parser.add_argument('--pilot', action='store_true')
    parser.add_argument('--json', action='store_true', help='Print the full report instead of the summary')
    args = parser.parse_args()
    try:
        report = run(args.symbol, pilot=args.pilot, diagnostics_only=args.symbol is None)
        print(json.dumps(report if args.json else summary(report), indent=2))
    except Exception as exc:
        print(json.dumps({'status': 'ERROR', 'error': type(exc).__name__, 'ordersSubmitted': False}))
        raise SystemExit(1)
