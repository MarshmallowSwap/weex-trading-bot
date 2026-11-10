"""Single minimum simulation TP-trigger mechanics test; does not test net profit."""
import copy,json,sys,time
from datetime import datetime,timezone
from decimal import Decimal as D,ROUND_CEILING
from pathlib import Path
ROOT=Path(r'D:\FUNDSHOT\weex_alerts')
if str(ROOT) not in sys.path:sys.path.append(str(ROOT))
import weex_simulation_trigger_trial as trial
c=trial.c
SCOPE='MINIMUM_SIMULATION_TECHNICAL_MARK_TRIGGER_300_SECONDS'
FOLDER=ROOT/'simulation_domain'/'technical_mark_trigger_buffer_20261023'

def technical_price(mark,tick):
    mark,tick=D(str(mark)),D(str(tick))
    if not mark.is_finite() or mark<=0 or tick!=D('.1'):
        raise ValueError('TECHNICAL_PRICE_SCOPE')
    return (mark*D('1.0002')/tick).to_integral_value(rounding=ROUND_CEILING)*tick+tick

class TechnicalLifecycle(c.SimulationCycleLifecycle):
    def prepare(self,signal_id,plan):
        plan=copy.deepcopy(plan)
        plan['takeProfitPolicy']='TECHNICAL_MARK_WITH_LATENCY_BUFFER_NOT_NET_PROFIT'
        return super().prepare(signal_id,plan)
    def reconcile(self,tid):
        item=self.get(tid)
        if (item['state'] not in ('CLOSED','REJECTED','SUPERSEDED') and not item.get('owned')
                and self.writes(tid).get('ENTRY')):
            try:
                order,fills,positions,algos,opened_algos=self.observations(item)
                qty,cost,fees=self.fills(order,fills)
                if order['status']=='FILLED':
                    if (qty!=D('.0001') or len(positions)!=1 or positions[0]['symbol']!='BTCUSDT'
                          or positions[0]['side']!='LONG' or D(positions[0]['size'])!=qty
                          or not positions[0].get('id') or algos or opened_algos):
                        raise ValueError('TECHNICAL_ENTRY_OWNERSHIP')
                    started=time.monotonic()
                    mark=c.public('/capi/v3/market/symbolPrice',symbol='BTCUSDT',priceType='MARK')
                    if time.monotonic()-started>5 or mark.get('symbol')!='BTCUSDT':
                        raise ValueError('TECHNICAL_MARK_UNVERIFIED')
                    snapshot={**mark,'sourceHost':c.SIM,'observedAt':datetime.now(timezone.utc).isoformat()}
                    trigger=technical_price(max(D(mark['price']),cost/qty),item['plan']['sizing']['priceTick'])
                    tp={'symbol':'BTCUSDT','clientAlgoId':item['plan']['tpClientId'],'planType':'TAKE_PROFIT',
                        'triggerPrice':format(trigger,'f'),'executePrice':'0','quantity':format(qty,'f'),
                        'positionSide':'LONG','triggerPriceType':'MARK_PRICE','reduceOnly':True,'closePosition':False}
                    owned={'positionId':str(positions[0]['id']),'quantity':str(qty),
                        'entryOrderId':str(order['orderId']),'actualEntryCostUSDT':str(cost),
                        'actualEntryFeesUSDT':str(fees),'tpRequest':tp}
                    state=self.gateway.state
                    state.update(technicalTriggerPolicy='MARK_WITH_LATENCY_BUFFER',technicalMarkSnapshot=snapshot,
                        profitTargetUnderTest=False,entryObservation=order,positionDuring=positions[0])
                    c.base.save(state)
                    self.state(tid,'ENTRY_FILLED',{'technicalTriggerOnly':True},owned=owned)
                else:
                    return self.state(tid,'ENTRY_PENDING',{'technicalEntryNotFullyFilled':True})
            except Exception as exc:
                return self.state(tid,'RECONCILIATION_PENDING',{'errorType':type(exc).__name__})
        return super().reconcile(tid)

def factory(state,folder):
    if state.get('cycleScope')!=SCOPE:raise PermissionError('TECHNICAL_TEST_SCOPE_REQUIRED')
    generic=c.engine_for(state,folder)
    engine=TechnicalLifecycle(generic.path,generic.gateway,generic.config_reader)
    engine.gateway.engine=engine
    return engine

def configure():
    trial.FOLDER=FOLDER;trial.SCOPE=SCOPE

def prepare():
    previous=json.loads((ROOT/'simulation_domain'/'technical_mark_trigger_20261023'/'journal.json').read_text())
    if previous['status']!='CLOSED_VERIFIED' or any(previous['finalInventory'].values()):
        raise PermissionError('NATURAL_TRIGGER_TRIAL_MUST_BE_CLOSED')
    configure();trial.prepare(engine_factory=factory)

def execute():
    configure();trial.execute(engine_factory=factory)

if __name__=='__main__':
    try:
        if sys.argv[1:]==['prepare']:prepare()
        elif sys.argv[1:]==['execute-authorized']:execute()
        else:raise PermissionError('EXPLICIT_TECHNICAL_TRIGGER_COMMAND_REQUIRED')
    except Exception as exc:
        print(json.dumps({'status':'REVIEW_REQUIRED','errorType':type(exc).__name__,
            'reason':str(exc) if type(exc) in (ValueError,PermissionError,RuntimeError) else 'SEE_JOURNAL'}))
        raise SystemExit(1)
