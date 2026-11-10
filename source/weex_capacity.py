"""Conservative API account capacity; no network or execution capability."""
from decimal import Decimal, InvalidOperation
import json, sqlite3
from contextlib import closing
from pathlib import Path


def full_closing_tp(order, positions):
    from weex_trailing import TYPES,normalize,number
    trailing=order.get('orderType',order.get('type')) in TYPES
    if trailing:
        try:
            order=normalize(order)
            if (number(order.get('activatePrice'))<=0
                    or not Decimal('.001')<=number(order.get('callbackRate'))<=Decimal('.9999')):
                return False
        except (ValueError,TypeError,ArithmeticError,KeyError):return False
    if (order.get('reduceOnly') is not True
            or order.get('orderType') not in ('TAKE_PROFIT_MARKET','TRAILING_MARKET')
            or order.get('algoStatus') not in ('NEW', 'UNTRIGGERED')):
        return False
    direction = order.get('positionSide')
    if direction not in ('LONG', 'SHORT'):
        return False
    if order.get('side') != ('SELL' if direction == 'LONG' else 'BUY'):
        return False
    matches = [p for p in positions if p.get('symbol') == order.get('symbol')
               and p.get('side') == direction]
    if len(matches) != 1:
        return False
    try:
        size = Decimal(str(matches[0]['size']))
        if not size.is_finite() or size <= 0:
            return False
        if order.get('closePosition') is True and not trailing:
            return True
        quantity = Decimal(str(order['quantity']))
        return quantity.is_finite() and quantity == size
    except (KeyError, ValueError, InvalidOperation):
        return False


def lifecycle_position_ids(database):
    """Return exact exchange position IDs owned by unresolved bot trades.

    None means the journal could not be read and callers must keep the
    conservative all-positions behavior. An empty set means a valid journal
    contains no active bot-owned positions.
    """
    try:
        with closing(sqlite3.connect(Path(database), timeout=2)) as conn:
            rows = conn.execute("""SELECT owned,plan FROM trades_v1
                WHERE state NOT IN ('CLOSED','REJECTED','SUPERSEDED')""").fetchall()
        result = set()
        for raw,raw_plan in rows:
            if not raw:
                continue
            owned = json.loads(raw)
            plan = json.loads(raw_plan) if raw_plan else {}
            source = owned.get('entrySource',plan.get('entrySource','automatic')) if isinstance(owned,dict) else 'automatic'
            if source == 'manual_telegram':
                continue
            position_id = owned.get('positionId') if isinstance(owned, dict) else None
            if position_id is not None:
                result.add(str(position_id))
        return result
    except (OSError, sqlite3.Error, ValueError, TypeError):
        return None


def account_capacity(positions, orders, managed_position_ids=None):
    if not isinstance(positions, list) or not isinstance(orders, list):
        raise ValueError('INVALID_CAPACITY_ACCOUNT')
    if any(not isinstance(r, dict) or not isinstance(r.get('symbol'), str)
           or not r['symbol'] for r in positions + orders):
        raise ValueError('INVALID_CAPACITY_ROWS')
    counted = [o for o in orders if not full_closing_tp(o, positions)]
    if managed_position_ids is None:
        managed = positions
        manual_excluded = 0
    else:
        owned_ids = {str(x) for x in managed_position_ids}
        managed = [p for p in positions if str(p.get('id')) in owned_ids]
        manual_excluded = len(positions) - len(managed)
    return {'count': len(managed) + len(counted),
            'positionCount': len(managed),
            'manualPositionsExcluded': manual_excluded,
            'symbols': sorted({r['symbol'] for r in positions + counted}),
            'excludedClosingTPs': len(orders) - len(counted)}
