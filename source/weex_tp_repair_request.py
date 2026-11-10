"""Build a deterministic WEEX replacement TP request, offline only.

Never dispatches an order. Preserves the original position's exit policy;
changing to current settings requires an independent, explicit strategy migration.
"""
import copy
from decimal import Decimal
from weex_tp_repair_simulator import client_id
from weex_http_guard import prepare_sdk_request

def build(proposal, trade):
    if proposal.get('eligible') is not True or proposal.get('dispatchAllowed') is not False:
        raise ValueError('REPAIR_GATE_NOT_APPROVED')
    owned=trade.get('owned') or {}
    original=owned.get('tpRequest')
    if not isinstance(original,dict):
        raise ValueError('NO_ORIGINAL_TP')
    if (proposal['tradeId']!=trade.get('id') or proposal['symbol']!=trade.get('symbol')
        or str(proposal['positionId'])!=str(owned.get('positionId'))):
        raise ValueError('REPAIR_BINDING_MISMATCH')
    side=original.get('positionSide')
    if side not in ('LONG','SHORT') or original.get('reduceOnly') is not True:
        raise ValueError('UNSAFE_CLOSE_DIRECTION')
    q=Decimal(str(original.get('quantity')))
    if not q.is_finite() or q<=0 or q!=Decimal(str(owned.get('quantity'))):
        raise ValueError('TP_QUANTITY_CHANGED')
    request=copy.deepcopy(original)
    request['clientAlgoId']=client_id(trade['id'],str(owned['positionId']))
    if request.get('symbol')!=trade['symbol']:
        raise ValueError('TP_SYMBOL_CHANGED')
    operation=owned.get('tpOperation','post_capi_v3_placeTpSlOrder')
    if operation=='post_capi_v3_placeTpSlOrder':
        if (request.get('planType')!='TAKE_PROFIT'
            or request.get('closePosition') is not False
            or request.get('triggerPriceType')!='MARK_PRICE'):
            raise ValueError('UNSAFE_FIXED_TP')
        trigger=Decimal(str(request.get('triggerPrice')))
        if not trigger.is_finite() or trigger<=0:
            raise ValueError('INVALID_TRIGGER')
    elif operation=='post_capi_v3_algoOrder':
        if (request.get('type')!='TRAILING_MARKET'
            or request.get('side')!=('SELL' if side=='LONG' else 'BUY')):
            raise ValueError('UNSAFE_TRAILING_TP')
    else:
        raise ValueError('UNSUPPORTED_TP_OPERATION')
    preview=prepare_sdk_request(operation,request)
    if preview.get('ordersSubmitted') is not False or preview.get('networkRequests')!=0:
        raise ValueError('PREVIEW_NOT_OFFLINE')
    return {'operation':operation,'request':request,'sdkPreview':preview,
            'dispatchAllowed':False,'source':'ORIGINAL_EXIT_POLICY'}
