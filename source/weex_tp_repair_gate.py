"""Fail-closed TP replacement eligibility. Pure data validation; NEVER dispatches orders."""
from decimal import Decimal, InvalidOperation

ACTIVE = frozenset(('NEW', 'UNTRIGGERED', 'TRIGGERED'))
CANCELLED = frozenset(('CANCELED', 'CANCELLED'))
def number(v):
    try:
        x = Decimal(str(v))
        if not x.is_finite() or x <= 0:
            raise ValueError('INVALID_AMOUNT')
        return x
    except (InvalidOperation, TypeError):
        raise ValueError('INVALID_AMOUNT')

def evaluate(trade, writes, positions, regular, open_algos, history, *, complete_history=False):
    """Returns eligibility for a *proposal*, never permission to execute a live order."""
    def blocked(reason):
        return {'eligible':False,'reason':reason,'dispatchAllowed':False}
    if not complete_history:
        return blocked('INCOMPLETE_HISTORY')
    owned = trade.get('owned') or {}
    plan = trade.get('plan') or {}
    if owned.get('entrySource', plan.get('entrySource')) != 'automatic':
        return blocked('NOT_AUTOMATIC_BOT_POSITION')
    if trade.get('state') not in ('PROTECTED','REVIEW_REQUIRED','ENTRY_FILLED','TP_PENDING'):
        return blocked('LIFECYCLE_STATE_UNSUPPORTED')
    ack = (writes.get('ENTRY') or {}).get('response')
    if not isinstance(ack, dict) or ack.get('success') is not True or str(ack.get('orderId'))!=str(owned.get('entryOrderId')):
        return blocked('ENTRY_PROOF_MISSING')
    symbol = trade.get('symbol')
    matching = [p for p in positions if p.get('symbol') == symbol]
    if len(matching)!=1 or str(matching[0].get('id'))!=str(owned.get('positionId')):
        return blocked('POSITION_ID_CHANGED')
    p = matching[0]
    if p.get('side') not in ('LONG','SHORT') or p.get('side') != (owned.get('tpRequest') or {}).get('positionSide'):
        return blocked('POSITION_SIDE_CHANGED')
    try:
        if (number(p.get('size')) != number(owned.get('quantity'))
            or number(p.get('openValue')) != number(owned.get('actualEntryCostUSDT'))
            or number(p.get('openFee')) != number(owned.get('actualEntryFeesUSDT'))):
            return blocked('POSITION_ECONOMICS_CHANGED')
    except ValueError:
        return blocked('INVALID_POSITION_ECONOMICS')
    if any(o.get('symbol')==symbol for o in regular):
        return blocked('REGULAR_ORDERS_PRESENT')
    if any(a.get('symbol')==symbol for a in open_algos):
        return blocked('ALGO_ORDER_PRESENT')
    # A new proposal can only be considered if every historical order for the
    # symbol is known to have ended without executing. Unknown/filled orders block.
    past = [a for a in history if a.get('symbol')==symbol]
    if not past:
        return blocked('MISSING_HISTORY_OF_PROTECTION')
    if any(a.get('algoStatus') not in CANCELLED for a in past):
        return blocked('HISTORY_NOT_PROVEN_CANCELLED')
    if any(a.get('actualOrderId') for a in past):
        return blocked('PRIOR_EXIT_EXECUTION_LINK')
    old_tp = writes.get('TP')
    if not old_tp or old_tp.get('state')!='RESPONSE_RECEIVED':
        return blocked('TP_DISPATCH_UNCERTAIN')
    old_client = (owned.get('tpRequest') or {}).get('clientAlgoId')
    if not old_client:
        return blocked('ORIGINAL_CLIENT_ID_MISSING')
    matching_old=[a for a in past if a.get('clientAlgoId')==old_client]
    if len(matching_old)!=1:
        return blocked('ORIGINAL_TP_NOT_UNIQUE')
    original_ack=old_tp.get('response')
    if isinstance(original_ack,list) and len(original_ack)==1:
        original_ack=original_ack[0]
    if (not isinstance(original_ack,dict) or original_ack.get('success') is not True
        or not original_ack.get('orderId')
        or str(original_ack['orderId'])!=str(matching_old[0].get('algoId'))):
        return blocked('ORIGINAL_TP_ACK_MISMATCH')
    return {'eligible':True,'reason':'CANCELLED_TP_CONFIRMED_PROPOSAL_ONLY',
            'tradeId':trade['id'],'symbol':symbol,'positionId':str(p['id']),
            'dispatchAllowed':False}
