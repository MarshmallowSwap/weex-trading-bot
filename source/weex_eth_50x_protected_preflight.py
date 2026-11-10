"""Read-only bounded ETH 50x crash pilot scope and atomic-stop payload factory.
NO order submission, leverage POST, Telegram action, or production activation.
"""
from decimal import Decimal as D, InvalidOperation, ROUND_DOWN
from pathlib import Path
import json
from weex_margin_sizing import contract_rules
from weex_pilot_attached_stop_evidence import positive
import live_control

ROOT=Path(__file__).resolve().parent
SYMBOL='ETHUSDT'
LEVERAGE=D(50)
MAX_NOTIONAL=D(5)
STOP_DISTANCE=D('0.015')
STOP_CEILING=D('0.025')

def scoped_preview(meta,brackets,book,account_symbol, *,root=ROOT):
    root=Path(root)
    cfg=json.loads((root/'weex_ai_risk_config.json').read_text(encoding='utf-8'))
    if live_control.state(root)['mode']!='STOPPED':
        raise PermissionError('PRODUCTION_BOT_MUST_STAY_STOPPED')
    if cfg['execution']['enabled'] is not False or cfg['execution']['mode']!='PRETRADE':
        raise PermissionError('PRODUCTION_ORDER_DISPATCH_MUST_BE_DISABLED')
    if cfg['risk']['minimumLeverage']!=50:raise PermissionError('EXPECTED_STRATEGY_FLOOR_50')
    if meta.get('symbol')!=SYMBOL:raise ValueError('UNEXPECTED_CONTRACT')
    rules=contract_rules(meta)
    if rules['maxLeverage']<LEVERAGE or rules['minLeverage']>LEVERAGE:
        raise ValueError('50X_NOT_ALLOWED_BY_METADATA')
    if not isinstance(brackets,list) or not any(
        D(str(t['notionalFloor']))<=rules['minQuantity']*D(str(book['bestAsk']))<D(str(t['notionalCap']))
        and D(str(t['initialLeverage']))>=LEVERAGE for t in brackets):
        raise ValueError('RISK_BRACKET_DOES_NOT_ALLOW_50X_MINIMUM')
    if (not isinstance(account_symbol,list) or len(account_symbol)!=1
        or account_symbol[0].get('symbol')!=SYMBOL
        or account_symbol[0].get('marginType') not in ('CROSS','CROSSED')
        or account_symbol[0].get('separatedType')!='COMBINED'):
        raise ValueError('CROSS_HEDGE_ACCOUNT_CONFIG_NOT_VERIFIED')
    if book.get('symbol')!=SYMBOL or book.get('status')!='OK' or book.get('depthUnitVerified') is not True:
        raise ValueError('LIVE_BOOK_NOT_CERTIFIED')
    bid=D(str(book['bestBid']));ask=D(str(book['bestAsk']))
    if not all(x.is_finite() and x>0 for x in (bid,ask)) or ask<=bid:
        raise ValueError('INVALID_LIVE_BID_ASK')
    qty=rules['minQuantity']
    if qty%rules['quantityStep']!=0:raise ValueError('MINIMUM_NOT_ALIGNED_TO_STEP')
    notional=qty*ask
    if notional>MAX_NOTIONAL:raise ValueError('MINIMUM_ORDER_EXCEEDS_TEST_NOTIONAL_CAP')
    tick=rules['priceTick']
    stop=(ask*(1-STOP_DISTANCE)/tick).to_integral_value(rounding=ROUND_DOWN)*tick
    if stop<=0 or not stop<bid:raise ValueError('INVALID_STOP')
    return {'status':'PREVIEW_ONLY','symbol':SYMBOL,'leverage':'50',
      'quantity':format(qty,'f'),'notionalUSDT':format(notional,'f'),
      'indicativeInitialMarginUSDT':format(notional/LEVERAGE,'f'),
      'stopTriggerPrice':format(stop,'f'),'stopWorkingType':'MARK_PRICE',
      'marginMode':'CROSSED','accountConfiguredLeverage':str(account_symbol[0].get('crossLeverage')),
      'leverageSetupRequired':D(str(account_symbol[0].get('crossLeverage',0)))!=LEVERAGE,
      'maxTestNotionalUSDT':format(MAX_NOTIONAL,'f'),
      'maxLossGuaranteed':False,'ordersSent':0,
      'executionAuthorized':False,
      'requirementsRemaining':['fresh empty account','set and readback CROSS 50x',
          'protected ENTRY with durable intent','controlled child crash after ACK',
          'independent exchange readback and exact reduce-only close']}

def live_preflight(root=ROOT):
    root=Path(root)
    if live_control.state(root)['mode']!='STOPPED' or live_control.build_errors(root):
        return {'status':'BLOCKED_CONTROL_OR_INTEGRITY','ordersSent':0}
    # GET-only; use the existing WEEX API rate governor. Never bypass a quota.
    try:
        from weex_simple_bot import public
        from weex_live_worker import Reader
        from orderbook_liquidity import inspect
        reader=Reader(root)
        positions,orders,algos=reader.account()
        if positions or orders or algos:
            return {'status':'ACCOUNT_NOT_EMPTY','ordersSent':0,
                    'positions':len(positions),'orders':len(orders),'conditional':len(algos)}
        metadata=public('/capi/v3/market/exchangeInfo',symbol=SYMBOL)
        meta=next(x for x in metadata['symbols'] if x['symbol']==SYMBOL)
        risk=public('/capi/v3/market/riskLimits',symbol=SYMBOL)
        brackets=next(x['brackets'] for x in risk if x['symbol']==SYMBOL)
        symbol_setting=reader.read('get_capi_v3_account_symbolConfig',symbol=SYMBOL)
        book=inspect(SYMBOL)
        preview=scoped_preview(meta,brackets,book,symbol_setting,root=root)
        preview['status']='AWAIT_50X_ACCOUNT_SETUP_AND_CRASH_EXECUTOR' if preview['leverageSetupRequired'] else 'AWAIT_PROTECTED_CRASH_EXECUTOR'
        preview['accountFlatVerified']=True
        preview['liveMarketReadback']=True
        preview['exchangeWrites']=0
        return preview
    except Exception as exc:
        return {'status':'PREFLIGHT_INCOMPLETE','errorType':type(exc).__name__,
          'errorCode':str(exc)[:90] if type(exc).__name__ in ('BudgetDeferred','ValueError','PermissionError') else None,
          'ordersSent':0,'executionAuthorized':False}

if __name__=='__main__':
    print(json.dumps(live_preflight(),ensure_ascii=False))
