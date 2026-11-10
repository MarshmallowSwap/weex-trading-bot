"""Candidate-only 50x, minimum-quantity real crash test scope. ZERO exchange writes.
No order can be sent by this program. Requires fresh live GETs for authorization.
"""
import json,sys
from pathlib import Path
from decimal import Decimal as D
import live_control
ROOT=Path(__file__).resolve().parent
MAX_NOTIONAL=D('5')
MAX_LEVERAGE=D('50')
def build(root=ROOT):
    root=Path(root)
    cfg=json.loads((root/'weex_ai_risk_config.json').read_text(encoding='utf-8'))
    assert live_control.state(root)['mode']=='STOPPED'
    assert cfg['risk']['minimumLeverage']==50
    assert cfg['execution']['enabled'] is False
    assert cfg['execution']['mode']=='PRETRADE'
    source=json.loads((root/'universe_latest.json').read_text(encoding='utf-8'))
    assert source['minLeverageFilter']==50
    choices=[]
    for row in source['symbols']:
        if D(str(row['maxLeverageAdvertised']))!=MAX_LEVERAGE:continue
        try:
            qty=D(str(row['minOrderSize']))
            precision=int(row['quantityPrecision'])
            step=D('1').scaleb(-precision)
            if qty<=0 or step<=0 or qty%step!=0:continue
            choices.append({'symbol':row['symbol'],'minimumQuantity':format(qty,'f'),
                 'quantityStep':format(step,'f'),'advertisedMaxLeverage':'50'})
        except (ValueError,ArithmeticError,KeyError,TypeError):continue
    return {'status':'AWAIT_FRESH_ACCOUNT_AND_MARKET_PREFLIGHT','realOrdersSent':0,
        'productionEnabled':False,'marginMode':'CROSS',
        'targetLeverage':'50','maxEntryNotionalUSDT':str(MAX_NOTIONAL),
        'maximumIndicativeMarginUSDT':str(MAX_NOTIONAL/MAX_LEVERAGE),
        'requiredSafety':['fresh complete empty account','contract and risk tier verified',
            'mark and ask/bid prices verified','min quantity x live price <= 5 USDT',
            'actual CROSS leverage is 50x with readback','native attached stop verified',
            'independently verified exact reduce-only close',
            'worker lifecycle intent persisted prior to POST'],
        'candidateCount':len(choices),'candidates':choices,
        'selection':'MINIMUM_EXCHANGE_QUANTITY_WITH_LIVE_PRICES_AND_FEES',
        'warning':'CROSS can expose all shared collateral, even when indicative position margin is small.'}
if __name__=='__main__':
    r=build()
    print(json.dumps({k:v for k,v in r.items() if k!='candidates'},ensure_ascii=False))
    print('EXAMPLE_CANDIDATES',json.dumps(r['candidates'][:8],ensure_ascii=False))
