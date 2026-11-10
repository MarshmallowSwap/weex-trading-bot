"""Exact WEEX attached-stop evidence for a journaled ETH pilot.

Supports observed API-SIM format (parent order omits SL fields; child carries
actualOrderId, clientAlgoId, workingType). Does not infer protection from ACK.
Any unrecognized/missing identity fails closed. No network or order writes.
"""
from decimal import Decimal,InvalidOperation

def positive(x):
    try:
        n=Decimal(str(x))
        return n if n.is_finite() and n>0 else None
    except (ValueError,InvalidOperation,TypeError):return None

def protected_entry(proposals,order,conditional,side,quantity):
    deny=lambda reason:{'verified':False,'reason':reason}
    if not isinstance(proposals,dict) or not isinstance(order,dict):
        return deny('ORDER_OR_JOURNAL_MISSING')
    if not isinstance(conditional,list) or len(conditional)!=1 or not isinstance(conditional[0],dict):
        return deny('EXACTLY_ONE_CONDITIONAL_STOP_REQUIRED')
    entry=proposals.get('entry')
    if not isinstance(entry,dict) or entry.get('SlWorkingType')!='MARK_PRICE':
        return deny('NO_MARK_STOP_IN_JOURNAL')
    cid=entry.get('newClientOrderId')
    oid=order.get('orderId')
    if (not isinstance(cid,str) or not cid.startswith('wxpilot_')
        or not oid or order.get('clientOrderId')!=cid
        or order.get('symbol')!='ETHUSDT'
        or order.get('positionSide')!=side
        or order.get('status')!='FILLED'
        or side not in ('LONG','SHORT')):
        return deny('PARENT_ENTRY_NOT_EXACT')
    price=positive(entry.get('slTriggerPrice'))
    qty=positive(quantity)
    c=conditional[0]
    actual_price=positive(c.get('triggerPrice'))
    actual_qty=positive(c.get('quantity'))
    if not price or not qty or actual_price!=price or actual_qty!=qty:
        return deny('EXCHANGE_STOP_PRICE_OR_SIZE_MISMATCH')
    if (c.get('symbol')!='ETHUSDT' or c.get('positionSide')!=side
        or c.get('side')!=('SELL' if side=='LONG' else 'BUY')
        or c.get('reduceOnly') is not True
        or c.get('orderType') not in ('STOP_MARKET','STOP_LOSS_MARKET')
        or c.get('algoStatus') not in ('NEW','UNTRIGGERED')
        or c.get('workingType')!='MARK_PRICE'):
        return deny('EXCHANGE_STOP_FIELDS_MISMATCH')
    # The actual WEEX API-SIM response links child to its filled parent.
    if (not c.get('algoId') or c.get('clientAlgoId')!=cid+'sl'
        or str(c.get('actualOrderId'))!=str(oid)):
        return deny('EXCHANGE_STOP_NOT_BOUND_TO_EXACT_ENTRY')
    return {'verified':True,'reason':'EXACT_EXCHANGE_ATTACHED_STOP_OBSERVED',
            'triggerPrice':str(price),'algoId':str(c['algoId']),
            'clientAlgoId':c['clientAlgoId']}
