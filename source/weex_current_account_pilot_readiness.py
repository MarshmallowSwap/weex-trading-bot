"""Evidence for a proposed pilot on the EXISTING WEEX account; no writes to exchange."""
import json,os
from pathlib import Path
from datetime import datetime,timezone
from decimal import Decimal
from weex_live_worker import Reader
import live_control
ROOT=Path(__file__).resolve().parent
def inspect(root=ROOT,reader=None):
 root=Path(root)
 assert live_control.state(root)['mode']=='STOPPED','LIVE_MUST_STAY_STOPPED'
 errors=live_control.build_errors(root)
 reader=reader or Reader(root)
 p,o,a=reader.account()
 fees=reader.read('get_capi_v3_account_commissionRate',symbol='ETHUSDT')
 symbols=reader.read('get_capi_v3_account_symbolConfig',symbol='ETHUSDT')
 balances=reader.read('get_capi_v3_account_balance')
 config=next((x for x in symbols if x.get('symbol')=='ETHUSDT'),None)
 usdt=next((x for x in balances if x.get('asset')=='USDT'),None)
 if not config or not usdt:raise ValueError('ACCOUNT_DATA_INCOMPLETE')
 available=Decimal(str(usdt['availableBalance']))
 taker=Decimal(str(fees['takerCommissionRate']))
 if available<0 or not 0<=taker<1:raise ValueError('INVALID_WEEX_ACCOUNT_VALUES')
 gate=json.loads((root/'live_release_gate_latest.json').read_text())
 pilot=json.loads((root/'weex_live_1x_pilot_config.json').read_text())
 stop_enabled=live_control.configuration(root)[0]['risk']['stopLoss']['enabled']
 candidate={
    'symbol':'ETHUSDT','maxOrders':1,'maxIndicativeNotionalUSDT':'5',
    'desiredLeverage':'1','preferredPilotMarginMode':'ISOLATED',
    'currentMarginMode':config.get('marginType'),
    'currentCrossLeverage':str(config.get('crossLeverage')),
    'isolatedLeverageAvailableInAccountConfig':str(config.get('isolatedLongLeverage')),
    'takerFeeRate':str(taker),
    'estimatedRoundTripTakerFeesOn5USDTNotional':str(Decimal(5)*taker*2),
    'stopLossActive':stop_enabled,'accountRiskIsolated':False,
    'orderMinimumNotionalAndTickVerified':False,
    'triggeredCloseAndReduceOnlyProven':False,
    'isolatedChangeAuthorizedOrPerformed':False,
    'orderDispatchAuthorized':False}
 blockers=['REAL_CRASH_RESTART_NOT_CERTIFIED','CURRENT_CROSS_COLLATERAL_EXPOSURE',
 'NO_STOP_LOSS','ISOLATED_PILOT_NOT_CONFIGURED','PILOT_ORDER_EXECUTION_NOT_APPROVED',
 'MIN_NOTIONAL_AND_CLOSE_PROTOCOL_NOT_VERIFIED']
 if gate.get('gate')!='GO':blockers.append('INDEPENDENT_RELEASE_GATE_NO_GO')
 if errors:blockers.append('CODE_INTEGRITY_ERROR')
 if p or o or a:blockers.append('EXISTING_EXPOSURE')
 result={'checkedAt':datetime.now(timezone.utc).isoformat(),'account':'CURRENT_WEEX_ACCOUNT',
 'purpose':'ONLY_REVIEW_AND_PREPARE_ONE_POSITION_PILOT',
 'currentUsdtAvailable':str(available),'existingPositions':len(p),
 'regularOrders':len(o),'conditionalOrders':len(a),
 'candidate':candidate,'blockers':sorted(blockers),'go':False,
 'maySendRealOrders':False,'exchangeWrites':0,
 'warning':'A five-USDT order under existing CROSS settings does NOT limit possible loss to five USDT; wallet collateral is shared.'}
 return result
if __name__=='__main__':
 result=inspect()
 path=ROOT/'weex_current_account_pilot_readiness_latest.json'
 tmp=path.with_suffix('.tmp')
 tmp.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
 os.replace(tmp,path)
 print(json.dumps(result,ensure_ascii=False))
