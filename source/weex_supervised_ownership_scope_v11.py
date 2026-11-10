"""Strict symbol/identity separation for supervised recovery CLOSE only.

Foreign symbols are visible in the audit but never candidates for a pilot
reduceOnly close. This module NEVER authorizes a new ENTRY on a shared CROSS
account; it intentionally requires complete, unambiguous exchange snapshots.
"""
from __future__ import annotations

class OwnershipScopeBlocked(ValueError):pass

def split_exact_symbol(positions,regular,conditional,*,symbol='ETHUSDT'):
    if not isinstance(symbol,str) or not symbol:
        raise OwnershipScopeBlocked('TARGET_SYMBOL_INVALID')
    rows=(positions,regular,conditional)
    if any(not isinstance(group,list) or any(not isinstance(x,dict) or
           not isinstance(x.get('symbol'),str) or not x['symbol'] for x in group)
           for group in rows):
        raise OwnershipScopeBlocked('INCOMPLETE_OR_INVALID_ACCOUNT_SNAPSHOT')
    target=tuple([[x for x in group if x['symbol']==symbol] for group in rows])
    foreign=tuple([[x for x in group if x['symbol']!=symbol] for group in rows])
    return {'targetPositions':target[0],'targetRegular':target[1],
       'targetConditional':target[2],
       'foreignPositions':foreign[0],'foreignRegular':foreign[1],
       'foreignConditional':foreign[2],
       'foreignExposurePresent':any(foreign),
       'foreignSymbols':sorted({x['symbol'] for group in foreign for x in group}),
       'entryAllowed':False,'networkWrites':0}
