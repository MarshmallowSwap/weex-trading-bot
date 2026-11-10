"""Real-account WEEX pilot entry coordinator.

This is the missing invocation link from the unified orchestrator to the
authenticated SDK order path. It does not enable any live flag; refusals are
explicit, and the initial GET evidence is consumed directly, not synthetic.
"""
import json
from pathlib import Path
from decimal import Decimal
from weex_live_worker import Reader,public
from orderbook_liquidity import inspect as inspect_book
from weex_margin_sizing import contract_rules
from weex_isolated_pilot_offline_journal import reserve
from weex_pilot_entry_sdk_adapter import PilotEntrySDKAdapter
from weex_pilot_guarded_entry_dispatch import send_entry_once
from weex_pilot_flat_baseline_readonly import capture
from weex_pilot_dispatch_readback_run import pending
import live_control

ROOT=Path(__file__).resolve().parent

def observe_account(root):
    root=Path(root)
    reader=Reader(root)
    positions,regular,conditional=reader.account()
    symbol_config=reader.read('get_capi_v3_account_symbolConfig',symbol='ETHUSDT')
    balances=reader.read('get_capi_v3_account_balance')
    if not all(isinstance(v,list) for v in (positions,regular,conditional,symbol_config,balances)):
        raise ValueError('AUTHENTICATED_READ_INCOMPLETE')
    if len(symbol_config)!=1 or symbol_config[0].get('symbol')!='ETHUSDT':
        raise ValueError('ETH_ACCOUNT_CONFIG_AMBIGUOUS')
    cfg=symbol_config[0]
    usd=next((b.get('availableBalance') for b in balances if b.get('asset')=='USDT'),None)
    if usd is None:raise ValueError('USDT_BALANCE_UNAVAILABLE')
    if cfg.get('separatedType')!='COMBINED':
        raise PermissionError('POSITION_MODE_UNEXPECTED')
    account={'fresh':True,'positions':positions,'regularOrders':regular,'conditionalOrders':conditional,
             'marginMode':cfg.get('marginType'),
             'isolatedLeverage':1 if str(cfg.get('isolatedLongLeverage'))=='1'
                 and str(cfg.get('isolatedShortLeverage'))=='1' else None}
    return account,Decimal(str(usd))

def prepare_entry(root,*,pilot_id,side='LONG',authorization=None):
    root=Path(root)
    cfg=json.loads((root/'weex_live_1x_pilot_config.json').read_text())
    if live_control.state(root)['mode']!='STOPPED' or live_control.build_errors(root):
        raise PermissionError('PRODUCTION_MUST_BE_STOPPED_AND_INTEGRITY_CLEAN')
    if (cfg.get('executionEnabled') is not True or cfg.get('liveOrderSubmissionAllowed') is not True
        or cfg.get('reduceOnlyCloseVerified') is not True or cfg.get('stopLossVerified') is not True
        or cfg.get('requireExplicitTestOrderApproval') is not True):
        raise PermissionError('PILOT_LIVE_ORDER_NOT_ENABLED_OR_EXCHANGE_STOP_AND_EXIT_UNVERIFIED')
    if authorization is None:
        raise PermissionError('EXACT_PILOT_ORDER_APPROVAL_REQUIRED')
    db=root/'weex_isolated_pilot.sqlite3'
    if db.is_file():
        import sqlite3
        with sqlite3.connect(str(db)) as c:
            tables={x[0] for x in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if 'pilot_v1' in tables and c.execute('SELECT COUNT(*) FROM pilot_v1').fetchone()[0]:
                raise PermissionError('PILOT_ALREADY_USED')
    if pending(db):raise PermissionError('PENDING_DISPATCH_OUTCOME_UNKNOWN')
    account,available=observe_account(root)
    if any(account[k] for k in ('positions','regularOrders','conditionalOrders')):
        raise PermissionError('EXISTING_ACCOUNT_EXPOSURE')
    if account['marginMode']!='ISOLATED' or account['isolatedLeverage']!=1:
        raise PermissionError('ACCOUNT_NOT_ISOLATED_1X')
    if available<Decimal('5'):raise PermissionError('INSUFFICIENT_AVAILABLE_USDT')
    book=inspect_book('ETHUSDT')
    if book.get('status')!='OK' or book.get('depthUnitVerified') is not True:
        raise PermissionError('ORDERBOOK_NOT_VERIFIED')
    ask=Decimal(str(book['bestAsk']))
    rules=contract_rules(public('/capi/v3/market/exchangeInfo',symbol='ETHUSDT')['symbols'][0])
    step=rules['quantityStep']
    qty=(Decimal('5')/ask/step).to_integral_value(rounding='ROUND_DOWN')*step
    if qty<rules['minQuantity'] or qty>rules['maxQuantity'] or qty*ask>Decimal('5'):
        raise PermissionError('PILOT_ORDER_OUT_OF_BOUNDS')
    # Fresh account snapshot is captured directly by authenticated GET.
    baseline=capture(root)
    if not baseline['snapshotVerified']:raise PermissionError('FLAT_BASELINE_NOT_CAPTURED')
    # The approver must approve one exact, stable payload including its client ID.
    # Reserving the journal creates the ID, but cannot transmit any order.
    tick=rules['priceTick']
    if side=='LONG':
        stop=(ask*Decimal('.97')/tick).to_integral_value(rounding='ROUND_DOWN')*tick
    elif side=='SHORT':
        stop=(ask*Decimal('1.03')/tick).to_integral_value(rounding='ROUND_UP')*tick
    else:
        raise PermissionError('PILOT_SIDE_UNSUPPORTED')
    reserved=reserve(db,pilot_id=pilot_id,side=side,quantity=str(qty),
            stop_price=str(stop))
    if reserved.get('reservedPreviously') is True:
        raise PermissionError('PILOT_ID_PREVIOUSLY_RESERVED_NO_RETRY')
    from contextlib import closing
    from weex_isolated_pilot_offline_journal import connect
    with closing(connect(db)) as conn:
        raw=conn.execute('SELECT proposals FROM pilot_v1 WHERE pilot_id=?',(pilot_id,)).fetchone()[0]
    from weex_pilot_attach_atomic_stop import attach
    payload=attach(db,pilot_id,stop=str(stop),reference_price=str(ask))
    from weex_pilot_exact_approval import exact_approval, approved
    approval=exact_approval(pilot_id,payload,ask)
    from weex_pilot_unapproved_void import void_unapproved
    try:
        accepted=authorization(approval) is True
    except Exception:
        cleanup=void_unapproved(db,pilot_id)
        raise PermissionError('EXACT_ENTRY_APPROVAL_FAILED:'+cleanup['reason']) from None
    if not accepted:
        cleanup=void_unapproved(db,pilot_id)
        raise PermissionError('EXACT_ENTRY_ORDER_APPROVAL_DENIED:'+cleanup['reason'])
    from weex_pilot_protected_entry_sdk import ProtectedEntryTransport
    adapter=ProtectedEntryTransport(root,authorization=lambda op,p:
        approved(authorization,approval,op,p))
    return send_entry_once(db,pilot_id,ask=str(ask),account=account,
                           transport=adapter,main_mode='STOPPED')
