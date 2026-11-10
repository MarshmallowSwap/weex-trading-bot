"""User-requested reconciliation. Only exact orphan TP cancellations are writable."""
import copy,hashlib,json,sqlite3,time
from contextlib import closing
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import live_control as control
from weex_lifecycle import Lifecycle,now,dump
from weex_execution_cycle import exclusive
from weex_execution_readonly import pages
from weex_api_budget import budget,recovery,BudgetDeferred
from weex_close_proof import prove,flat_and_orphan,verify_bot_exit,fills as checked_fills,number

ACTIVE=('RUNNING','WAIT_API','VERIFYING')
TERMINAL=('CLOSED','REJECTED','SUPERSEDED')
HOST='https://api-contract.weex.com'

def save_status(root,result):
    path=Path(root)/'weex_reconcile_latest.json';tmp=path.with_suffix('.tmp')
    tmp.write_text(json.dumps(result,indent=2),encoding='utf-8');tmp.replace(path)

def tp_ack(engine,item):
    record=engine.writes(item['id']).get('TP') or {};ack=record.get('response')
    if record.get('payload')!=item['owned']['tpRequest']:raise ValueError('TP_INTENT_MISMATCH')
    if isinstance(ack,list):ack=ack[0] if len(ack)==1 else None
    if (record.get('state')!='RESPONSE_RECEIVED' or not isinstance(ack,dict)
        or ack.get('success') is not True or not ack.get('orderId')):raise ValueError('TP_ACK_UNVERIFIED')
    return str(ack['orderId'])

class Reconciler:
    def __init__(self,root,reader,stop_state,progress,timeout=1200,order_ids=()):
        self.root=Path(root);self.reader=reader;self.stop_state=copy.deepcopy(stop_state);self.progress=progress
        self.deadline=time.monotonic()+timeout;self.current=None;self.proof=None;self.backup=None;self.order_ids=tuple(order_ids)
        self.engine=Lifecycle(self.root/'weex_user_live_lifecycle.sqlite3',self,
            lambda:{'execution':{'enabled':True,'mode':'LIVE'}})
    def stopped(self):
        if self.stop_state['mode']!='STOPPED' or control.state(self.root)!=self.stop_state:
            raise ValueError('CONTROL_CHANGED')
        if time.monotonic()>self.deadline:raise ValueError('RECONCILE_TIMEOUT')
    def wait_budget(self,weight):
        while True:
            self.stopped();b=budget();b.ensure_limits()
            delay=max(0,b.ready_at(weight=weight)-b.clock(),b.used()['pauseUntil']-b.clock())
            if delay<=0:return
            self.progress('WAIT_API',waitSeconds=round(delay));time.sleep(min(10,delay+0.1))
    def account(self):
        while True:
            self.wait_budget(20);started=now()
            try:rows=self.reader.account()
            except BudgetDeferred:continue
            if now()-started>5000:raise ValueError('ACCOUNT_SNAPSHOT_STALE')
            self.account_at=started
            return rows
    def backup_once(self):
        if self.backup:return
        folder=self.root/'reconciliation_backups';folder.mkdir(exist_ok=True)
        self.backup=folder/('ledger-'+str(now())+'.sqlite3')
        with closing(sqlite3.connect(self.engine.path)) as src,closing(sqlite3.connect(self.backup)) as dst:src.backup(dst)
    def gather(self,item):
        end=now();symbol=item['symbol'];ack=tp_ack(self.engine,item)
        evidence={'orders':[],'fills':{},'historyEndMs':end,'botExitIds':[],'algos':[]}
        try:
            with recovery():orders=pages(self.reader.read,'get_capi_v3_order_history',identity='orderId',start=0,
                symbol=symbol,startTime=item['created']-1000,endTime=end)
            by_id={str(o['orderId']):o for o in orders}
            def add_order(order):
                if not isinstance(order,dict) or order.get('symbol')!=symbol or not order.get('orderId'):
                    raise ValueError('ORDER_SYMBOL_MISMATCH')
                key=str(order['orderId'])
                if key in by_id:
                    fields=('symbol','clientOrderId','side','positionSide','type','status','executedQty','reduceOnly','cumQuote')
                    if any(by_id[key].get(k)!=order.get(k) for k in fields):raise ValueError('ORDER_OBSERVATION_CHANGED')
                by_id[key]=order
            # The regular history can omit filled conditional orders. Fetch the
            # exact TP via its own history and acknowledgement, never by price.
            with recovery():
                prior=self.reader.read('get_capi_v3_allAlgoOrders',symbol=symbol,
                    startTime=item['created']-1000,endTime=end,limit=1000)
            if not isinstance(prior,dict) or prior.get('hasMore') is not False or not isinstance(prior.get('orders'),list):
                raise ValueError('INCOMPLETE_ALGO_HISTORY')
            algos=prior['orders']
            from weex_trailing import is_trailing,HISTORY_OPERATION,merge
            if is_trailing(item['plan']):
                with recovery():trails=pages(self.reader.read,HISTORY_OPERATION,identity='orderId',start=0,
                    symbol=symbol,startTime=item['created']-1000,endTime=end)
                algos=merge(algos,trails)
            evidence['algos']=algos
            matched=[a for a in algos if str(a.get('algoId'))==ack]
            if len(matched)>1:raise ValueError('AMBIGUOUS_TP_HISTORY')
            if matched and matched[0].get('algoStatus') in ('FILLED','TRIGGERED'):
                algo=matched[0];oid=str(algo.get('actualOrderId') or algo['algoId'])
                with recovery():order=self.reader.read('get_capi_v3_order',orderId=oid)
                evidence['botExitIds']=[verify_bot_exit(item,algo,order,ack)];add_order(order)
            if item['owned']['entryOrderId'] not in by_id:
                with recovery():add_order(self.reader.read('get_capi_v3_order',orderId=item['owned']['entryOrderId']))
            for oid in self.order_ids:
                with recovery():order=self.reader.read('get_capi_v3_order',orderId=oid)
                if str(order.get('orderId'))!=oid:raise ValueError('SUPPLIED_ORDER_ID_MISMATCH')
                add_order(order)
            orders=list(by_id.values());evidence['orders']=orders
            def get_fills(o):
                with recovery():return self.reader.read('get_capi_v3_userTrades',symbol=symbol,orderId=o['orderId'],limit=100)
            with ThreadPoolExecutor(4) as pool:
                jobs={str(o['orderId']):pool.submit(get_fills,o) for o in orders if number(o.get('executedQty',0))>0}
                evidence['fills']={key:f.result() for key,f in jobs.items()}
            evidence['proof']=prove(item,orders,evidence['fills'],evidence['botExitIds'])
            proof=evidence['proof']
            if proof.get('botTPUsed'):proof['tpId']=ack
            if len(proof['exitOrderIds'])==1:proof['exitOrderId']=proof['exitOrderIds'][0]
            return evidence
        except (ValueError,KeyError,TypeError,ArithmeticError) as exc:
            evidence['reason']=str(exc) if isinstance(exc,ValueError) else type(exc).__name__
            raise
        finally:
            folder=self.root/'weex_reconcile_details';folder.mkdir(exist_ok=True)
            path=folder/(hashlib.sha256(item['id'].encode()).hexdigest()+'.json')
            evidence.update(tradeId=item['id'],symbol=symbol,expectedQuantity=item['owned']['quantity'],checkedAt=control.timestamp())
            path.write_text(json.dumps(evidence,indent=2),encoding='utf-8')
    def write(self,operation,payload):
        """SDK session scoped to one owned cancellation, rechecked at dispatch."""
        item=self.current
        if not item or not self.proof:raise PermissionError('NO_EXTERNAL_CLOSE_PROOF')
        oid=tp_ack(self.engine,item)
        if operation!='delete_capi_v3_algoOrder' or payload!={'query':{'orderId':oid}}:
            raise PermissionError('ONLY_EXACT_ORPHAN_CANCEL')
        record=self.engine.writes(item['id']).get('CANCEL_EXTERNAL_TP') or {}
        if record.get('state')!='UNKNOWN' or record.get('payload')!=payload:raise PermissionError('DURABLE_CANCEL_REQUIRED')
        parent=self
        class Session:
            used=False
            def request(self,method,url,**kw):
                if self.used or method!='DELETE' or url!=HOST+'/capi/v3/algoOrder?orderId='+oid:
                    raise PermissionError('EXACT_CANCEL_URL_REQUIRED')
                if kw.get('data') not in (None,'',b'') or kw.get('json') or kw.get('params'):
                    raise PermissionError('UNEXPECTED_BODY')
                self.used=True;parent.stopped()
                if parent.engine.get(item['id'])['owned']!=item['owned']:raise ValueError('OWNERSHIP_CHANGED')
                fresh=parent.account();matched=flat_and_orphan(item,fresh,oid)
                if not matched:raise ValueError('ORPHAN_NO_LONGER_OPEN')
                parent.stopped()
                import requests
                with requests.Session() as network:
                    kw['allow_redirects']=False;budget().reserve(method,url)
                    response=network.request(method,url,**kw)
                    budget().observe(response.status_code,response.headers,url)
                    if response.status_code!=200:raise ValueError('CANCEL_UNCERTAIN')
                    return response
            def close(self):pass
        from weex_http_guard import sdk_types
        config,contract,_=sdk_types();cred=json.loads((self.root/'weex_credentials.json').read_text(encoding='utf-8'))
        client=contract(config_rest_api=config(base_path=HOST,api_key=cred['api_key'],api_secret=cred['secret_key'],
            passphrase=cred['passphrase'],session=Session(),timeout=10,max_retries=0))
        return client.rest_api.execute_operation(operation,payload).data
    def reconcile_one(self,tid):
        item=self.engine.get(tid)
        if item['state'] in TERMINAL:return {'symbol':item['symbol'],'state':'ALREADY_TERMINAL'}
        if not item.get('owned'):return {'symbol':item['symbol'],'state':'REVIEW_REQUIRED','reason':'OWNERSHIP_PROOF_MISSING'}
        if (item['plan'].get('liveAuthorizationScope')!='USER_ACTIVATED_LIVE_V1'
            or (item['plan'].get('authorization') or {}).get('host')!=HOST):raise ValueError('LIVE_SCOPE_REQUIRED')
        rows=self.account()
        if any(p['symbol']==item['symbol'] for p in rows[0]):
            return {'symbol':item['symbol'],'state':'POSITION_OPEN'}
        self.wait_budget(100);self.progress('RUNNING',symbol=item['symbol'])
        evidence=self.gather(item);ack=tp_ack(self.engine,item)
        orphan=flat_and_orphan(item,self.account(),ack)
        self.stopped();self.backup_once()
        with closing(self.engine.db()) as c,c:
            c.execute('''CREATE TABLE IF NOT EXISTS external_close_evidence_v1(
                trade_id TEXT PRIMARY KEY,proof_sha256 TEXT NOT NULL,proof TEXT NOT NULL,
                previous_record TEXT NOT NULL,recorded_at INTEGER NOT NULL)''')
            c.execute('INSERT OR REPLACE INTO external_close_evidence_v1 VALUES(?,?,?,?,?)',
                (tid,evidence['proof']['evidenceSha256'],dump(evidence),dump(item),now()))
        if orphan:
            self.current=item;self.proof=evidence
            self.engine.send_once(tid,'CANCEL_EXTERNAL_TP','delete_capi_v3_algoOrder',{'query':{'orderId':ack}})
        rows=self.account();observed=now()
        if flat_and_orphan(item,rows,ack):raise ValueError('ORPHAN_STILL_OPEN_NO_RETRY')
        self.stopped()
        detail={**evidence['proof'],'currentFlatAccountConfirmed':True,'currentFlatAccountSnapshotAtMs':observed,
            'residualOrdersAbsent':True,'reconciledAtUTC':control.timestamp()}
        with closing(self.engine.db()) as c,c:
            c.execute('BEGIN IMMEDIATE')
            current=c.execute('SELECT state,owned FROM trades_v1 WHERE id=?',(tid,)).fetchone()
            if current['state']!=item['state'] or json.loads(current['owned'])!=item['owned']:raise ValueError('JOURNAL_CHANGED')
            c.execute('UPDATE trades_v1 SET state=?,detail=?,updated=? WHERE id=?',('CLOSED',dump(detail),now(),tid))
            self.engine.event(c,tid,'CLOSED',detail)
        return {'symbol':item['symbol'],'state':'CLOSED_BOT_TP' if detail.get('botTPUsed') else 'CLOSED_EXTERNAL','orphanRemoved':orphan is not None}

def run(root,user,chat,*,reader=None,refresh=None,symbol=None,order_ids=()):
    root=Path(root)
    if symbol:
        from weex_trading_modes import normalize_symbol
        symbol=normalize_symbol(symbol)
    if len(order_ids)>5 or any(not isinstance(oid,str) or not oid.isascii() or not oid.isdigit() or not 1<=len(oid)<=20 for oid in order_ids) or (order_ids and not symbol):
        raise ValueError('INVALID_CLOSE_ORDER_IDS')
    result={'checkedAt':control.timestamp(),'status':'RUNNING','items':[]}
    def progress(status,**extra):
        result.update(status=status,checkedAt=control.timestamp(),**extra);save_status(root,result)
    from weex_live_worker import Reader,protected_unchanged,capacity,report
    def default_refresh(r):
        # Pure readback: never call Lifecycle.reconcile/send_once here. A missing
        # TP on a still-open position must remain available to normal recovery.
        rows=r.account();started=r.account_at;r.stopped();recovered=[];clear=True
        for item in r.engine.states():
            if item['state'] in TERMINAL:continue
            valid=protected_unchanged(r.engine,item['id'],rows,started)
            clear=clear and valid
            recovered.append({'tradeId':item['id'],'state':item['state'],
                'detail':{'verification':'SHARED_ACCOUNT_SNAPSHOT'} if valid else {'reason':'POSITION_OR_TP_NEEDS_FULL_RECOVERY'}})
        try:cap=capacity(rows,root,notify_missing=False)
        except ValueError as exc:
            return report(root,'BLOCKED_RECOVERY',accountReadOK=True,recoveryClear=False,reason=str(exc),recovered=recovered)
        return report(root,'DISARMED_READY' if clear else 'BLOCKED_RECOVERY',
            accountReadOK=True,recoveryClear=clear,capacity=cap,recovered=recovered,opened=[],entryAttempts=[])
    try:
        with exclusive(root/'weex_reconcile.lock'):
            # A concurrent scheduled cycle finishes before STOP and reconciliation.
            deadline=time.monotonic()+30
            while True:
                try:
                    lock=exclusive(root/'weex_live_worker.lock');lock.__enter__();break
                except RuntimeError as exc:
                    if str(exc)!='CYCLE_ALREADY_RUNNING' or time.monotonic()>deadline:raise
                    time.sleep(.5)
            try:
                if control.build_errors(root):raise ValueError('BUILD_NOT_VERIFIED')
                control.stop(user,chat,root);state=control.state(root)
                from weex_trading_modes import cancel_pending_manual
                cancel_pending_manual(root,'USER_RECONCILIATION')
                progress('RUNNING');r=Reconciler(root,reader or Reader(root),state,progress,order_ids=order_ids)
                for item in r.engine.states():
                    if item['state'] in TERMINAL or (symbol and item['symbol']!=symbol):continue
                    try:row=r.reconcile_one(item['id'])
                    except (ValueError,KeyError,TypeError,ArithmeticError,BudgetDeferred) as exc:
                        reason=str(exc) if isinstance(exc,(ValueError,BudgetDeferred)) else type(exc).__name__
                        row={'symbol':item['symbol'],'state':'REVIEW_REQUIRED','reason':reason}
                    result['items'].append(row);progress('RUNNING')
                    r.stopped()
                r.wait_budget(30);progress('VERIFYING')
                r.stopped();verified=refresh() if refresh else default_refresh(r)
                result['accountReadOK']=verified.get('accountReadOK') is True
                result['recoveryClear']=verified.get('recoveryClear') is True
                result['workerStatus']=verified.get('status')
                good=result['accountReadOK'] and result['recoveryClear'] and not any(x['state']=='REVIEW_REQUIRED' for x in result['items'])
                progress('DONE' if good else 'REVIEW_REQUIRED')
                return result
            finally:lock.__exit__(None,None,None)
    except RuntimeError as exc:
        if str(exc)=='CYCLE_ALREADY_RUNNING':return {'status':'BUSY','items':[]}
        progress('ERROR',reason=type(exc).__name__);return result
    except Exception as exc:
        progress('ERROR',reason=str(exc) if isinstance(exc,ValueError) else type(exc).__name__);return result

def message(result):
    if result['status']=='BUSY':return 'Riconciliazione o ciclo del bot già in corso. Attendi il risultato o riprova tra poco.'
    lines=['Riconciliazione completata.' if result['status']=='DONE' else 'Riconciliazione: restano verifiche da completare.']
    labels={'CLOSED_BOT_TP':'chiusura tramite TP del bot verificata e registrata','CLOSED_EXTERNAL':'chiusura esterna verificata e registrata','POSITION_OPEN':'posizione ancora aperta, conservata',
        'ALREADY_TERMINAL':'già riconciliata','REVIEW_REQUIRED':'da verificare'}
    for row in result.get('items',[]):
        text=row['symbol']+': '+labels.get(row['state'],row['state'])
        if row.get('orphanRemoved'):text+='; TP residuo rimosso'
        if row.get('reason'):text+=' — '+reason_text(row['reason'])
        lines.append(text+'.')
        if row['state']=='REVIEW_REQUIRED':lines.append(next_action(row['symbol'],row.get('reason')))
    if result.get('reason'):lines.append('Motivo: '+result['reason'])
    lines.append('Nuovi ingressi fermi. Usa /live_start e conferma per ripartire.' if result['status']=='DONE'
                 else 'Usa /blocchi per quantità, ordini e azioni disponibili. Il live resta fermo finché il recupero non è verificato.')
    return '\n'.join(lines)


def next_action(symbol,reason):
    command='/risolvi '+symbol.removesuffix('USDT')
    if reason in ('CLOSE_QUANTITY_MISMATCH','ENTRY_NOT_FOUND','INCOMPLETE_FILLS','INCOMPLETE_QUANTITY'):
        return ('Azione: '+command+'. Se manca una chiusura manuale, copia il suo ID dallo storico WEEX e invia '
                +command+' ID_ORDINE. Il bot verificherà ordine, quantità ed eseguiti prima di registrarlo.')
    if reason in ('POSITION_PRESENT','REGULAR_ORDER_PRESENT','ORPHAN_NOT_EXACT_OWNED_TP','OTHER_CONDITIONAL_ORDER'):
        return 'Sono presenti esposizioni o ordini diversi da quelli attesi. Usa /blocchi '+symbol.removesuffix('USDT')+' per identificarli; dopo averli verificati su WEEX, ripeti '+command+'.'
    if reason and ('BUDGET' in reason or 'TIMEOUT' in reason or 'STALE' in reason):
        return 'Verifica rinviata per dati o quota API. Riprova '+command+' quando la quota si libera.'
    return 'Usa /blocchi '+symbol.removesuffix('USDT')+' per il dettaglio e '+command+' per ricostruire nuovamente ordini ed eseguiti.'

def keyboard(result):
    buttons=[]
    for row in result.get('items',[]):
        if row['state']=='REVIEW_REQUIRED':
            buttons.append([{'text':'Risolvi '+row['symbol'].removesuffix('USDT'),'callback_data':'livectl:resolve:'+row['symbol']}])
    buttons.append([{'text':'Dettaglio blocchi','callback_data':'livectl:blocks'}])
    if result.get('status')=='DONE':buttons.append([{'text':'Prepara avvio LIVE','callback_data':'livectl:start'}])
    buttons=buttons[:12]
    buttons.append([{'text':'Simbolo / ID ordine','callback_data':'desk:resolve'}])
    buttons.append([{'text':'Stato e recupero','callback_data':'desk:recovery'},
                    {'text':'Menu principale','callback_data':'aimenu:home'}])
    return {'inline_keyboard':buttons}

def diagnostics(root,symbol=None):
    root=Path(root)
    if symbol:
        from weex_trading_modes import normalize_symbol
        symbol=normalize_symbol(symbol)
    path=root/'weex_user_live_lifecycle.sqlite3'
    if not path.exists():return 'Registro non disponibile. Usa /riconcilia per avviare i controlli.'
    with closing(sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True)) as c:
        c.row_factory=sqlite3.Row
        records=[dict(x) for x in c.execute("SELECT id,symbol,state,owned,detail FROM trades_v1 WHERE state NOT IN ('CLOSED','REJECTED','SUPERSEDED')")]
    try:latest=json.loads((root/'weex_reconcile_latest.json').read_text(encoding='utf-8'))
    except (OSError,ValueError):latest={}
    lines=['Dettaglio riconciliazione:']
    for row in records:
        if symbol and row['symbol']!=symbol:continue
        if row['state']=='PROTECTED' and not symbol:continue
        own=json.loads(row['owned'] or '{}');detail=json.loads(row['detail'] or '{}')
        last=next((x for x in latest.get('items',[]) if x['symbol']==row['symbol']),{})
        reason=last.get('reason') or detail.get('reason') or detail.get('error') or row['state']
        lines.extend([row['symbol']+' — '+reason_text(reason),'Quantità registrata: '+str(own.get('quantity','non disponibile')),
                      'Ordine ingresso: '+str(own.get('entryOrderId','non disponibile'))])
        try:
            proof=json.loads((root/'weex_reconcile_details'/(hashlib.sha256(row['id'].encode()).hexdigest()+'.json')).read_text(encoding='utf-8'))
            closed=number(0);ids=[]
            for o in proof.get('orders',[]):
                if str(o['orderId'])==str(own.get('entryOrderId')) or o.get('reduceOnly') is not True:continue
                try:q,_,_=checked_fills(o,proof['fills'][str(o['orderId'])])
                except (ValueError,KeyError,TypeError,ArithmeticError):continue
                closed+=q;ids.append(str(o['orderId']))
            lines.extend(['Quantità degli eseguiti di chiusura trovati: '+str(closed),
                          'Ordini chiusura trovati: '+(', '.join(ids) or 'nessuno'),'Ultima lettura: '+proof['checkedAt']])
        except (OSError,ValueError,KeyError,TypeError):pass
        lines.append(next_action(row['symbol'],reason))
    if len(lines)==1:lines.append('Nessun blocco di posizione trovato nel registro. Usa /riconcilia per verificare il conto e aggiornare la prontezza LIVE.')
    return '\n'.join(lines)[:3900]


def reason_text(reason):
    labels={
        'CLOSE_QUANTITY_MISMATCH':'gli eseguiti trovati non coprono tutta la quantità registrata',
        'INCOMPLETE_FILLS':'gli eseguiti ricevuti sono incompleti',
        'INCOMPLETE_QUANTITY':'mancano eseguiti per completare la quantità dell’ordine',
        'INCOMPLETE_ALGO_HISTORY':'WEEX ha restituito uno storico TP incompleto',
        'ORDER_SYMBOL_MISMATCH':'l’ordine indicato appartiene a un altro simbolo',
        'ORDER_OBSERVATION_CHANGED':'lo stesso ordine presenta dati discordanti nelle letture',
        'BOT_TP_HISTORY_MISMATCH':'il TP storico non coincide con quello registrato dal bot',
        'POSITION_PRESENT':'la posizione è ancora aperta su WEEX',
        'OTHER_CONDITIONAL_ORDER':'sono presenti altri ordini condizionati da identificare',
        'REGULAR_ORDER_PRESENT':'è presente un ordine ordinario ancora aperto',
        'ORPHAN_STILL_OPEN_NO_RETRY':'la cancellazione non è confermata; il TP risulta ancora aperto',
    }
    return labels.get(reason,reason)+' ('+reason+')' if reason in labels else reason
