"""Read-only live proof that foreign positions are not eligible for ETH supervised close."""
from pathlib import Path
import json,time
from weex_live_worker import Reader
from weex_supervised_ownership_scope_v11 import split_exact_symbol
import live_control
root=Path(__file__).resolve().parent
p,o,a=Reader(root).account()
scope=split_exact_symbol(p,o,a)
result={'checkedAtEpoch':time.time(),
 'status':'ETH_RECOVERY_SCOPE_DISJOINT_LIVE_READBACK',
 'foreignSymbols':scope['foreignSymbols'],
 'foreignPositions':len(scope['foreignPositions']),
 'foreignRegularOrders':len(scope['foreignRegular']),
 'foreignConditionalOrders':len(scope['foreignConditional']),
 'targetPositions':len(scope['targetPositions']),
 'targetRegularOrders':len(scope['targetRegular']),
 'targetConditionalOrders':len(scope['targetConditional']),
 'manualAINNotSelectedForETHClose':all(x['symbol']!='ETHUSDT'
    for x in scope['foreignPositions']+scope['foreignRegular']+scope['foreignConditional']),
 'entryAllowed':False,'closeAllowed':False,'exchangeWrites':0,
 'botMode':live_control.state(root)['mode']}
print(json.dumps(result,sort_keys=True))
