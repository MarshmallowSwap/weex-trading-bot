"""Pure local read-only audit. Never imports execution, Telegram or network code.

Historical economics are compared with their immutable per-trade plan, not the
current strategy. The caller owns persistence, scheduling and notification dedup.
"""
import json
import sqlite3
import time
from contextlib import closing
from datetime import datetime, timezone
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
from pathlib import Path

VERSION = 1
EPS = Decimal('0.0000001')


def num(value):
    value = Decimal(str(value))
    if not value.is_finite():
        raise ValueError('NONFINITE_NUMBER')
    return value


def stamp(seconds):
    return datetime.fromtimestamp(seconds, timezone.utc).isoformat()


def decoded(value):
    return json.loads(value) if value else {}


def _read(root):
    path = root / 'weex_user_live_lifecycle.sqlite3'
    if not path.is_file():
        raise FileNotFoundError('JOURNAL_MISSING')
    # An explicit read transaction gives tables a consistent snapshot while the
    # independent live worker continues writing. No schema or journal changes.
    with closing(sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True, timeout=2)) as c:
        c.row_factory = sqlite3.Row
        c.execute('BEGIN')
        trades = [dict(r) for r in c.execute('SELECT id,symbol,state,plan,owned,detail,created,updated FROM trades_v1')]
        writes = [dict(r) for r in c.execute('SELECT trade_id,kind,state,payload,response,at FROM writes_v1')]
        proofs = {}
        if c.execute("SELECT 1 FROM sqlite_master WHERE name='external_close_evidence_v1'").fetchone():
            proofs = {r[0]: decoded(r[1]) for r in c.execute('SELECT trade_id,proof FROM external_close_evidence_v1')}
    for t in trades:
        for field in ('plan', 'owned', 'detail'):
            t[field] = decoded(t[field])
            if not isinstance(t[field], dict):
                raise ValueError('JOURNAL_OBJECT_SCHEMA')
    for w in writes:
        for field in ('payload', 'response'):
            w[field] = decoded(w[field])
    return trades, writes, proofs


def _ack_id(write):
    if not write or write.get('state') != 'RESPONSE_RECEIVED':
        return None
    response = write.get('response')
    if isinstance(response, list):
        if len(response) != 1:
            return None
        response = response[0]
    if isinstance(response, dict) and response.get('success') is True and response.get('orderId'):
        return str(response['orderId'])
    return None


def audit(root, now=None):
    """Return JSON-compatible observations and stable findings; no writes/sends.

    now is Unix seconds, injectable for reproducible offline tests. A closed
    cached report is historical evidence even when old, but cannot certify the
    current account or a finalized ledger. No all-time completeness is implied.
    """
    root = Path(root)
    now = time.time() if now is None else float(now)
    findings = []
    symbols = {}

    def finding(tid, code, severity, evidence, recommendation):
        if tid in symbols:
            evidence = dict(evidence, symbol=symbols[tid])
        findings.append({'key': 'closed_quality:' + tid + ':' + code,
                         'severity': severity, 'code': code,
                         'evidence': evidence, 'recommendation': recommendation})

    result = {'version': VERSION, 'checkedAt': stamp(now), 'status': 'OK',
              'mode': 'READ_ONLY_LOCAL', 'networkRequests': 0, 'exchangeWrites': 0,
              'trades': [], 'findings': findings,
              'coverage': {'scope': 'Executed user-live journal plus available local closed report',
                           'allTimeAccountHistoryVerified': False, 'fundingComplete': False,
                           'signalHistoryReplayable': False}}
    try:
        trades, writes, proofs = _read(root)
        symbols.update({t['id']: t['symbol'] for t in trades})
    except (OSError, sqlite3.Error, ValueError, TypeError) as exc:
        result['status'] = 'UNAVAILABLE'
        finding('source', 'JOURNAL_UNAVAILABLE', 'ERROR', {'errorType': type(exc).__name__},
                'Verificare accesso e schema del journal; non dedurre che il conto sia vuoto.')
        return result

    report = {}
    report_path = root / 'telegram_positions_closed.json'
    if report_path.is_file():
        try:
            report = json.loads(report_path.read_text(encoding='utf-8'))
            if (not isinstance(report, dict) or not isinstance(report.get('rows'), list)
                    or any(not isinstance(r, dict) for r in report['rows'])):
                raise ValueError('REPORT_SCHEMA')
        except (OSError, ValueError, TypeError):
            report = {}
            finding('source', 'CLOSED_REPORT_UNREADABLE', 'WARNING', {},
                    'Conservare un report locale valido; le riconciliazioni già registrate restano utilizzabili.')
    result['coverage'].update(reportObservedAtMs=report.get('observedAtMs'),
                              reportWindowStartMs=report.get('windowStartMs'),
                              reportWindowEndMs=report.get('windowEndMs'),
                              reportStale=report.get('stale'),
                              journalRows=len(trades))
    matched_report_indices = set()
    executed = 0
    for t in trades:
        tid = t['id']
        own_writes = {w['kind']: w for w in writes if w['trade_id'] == tid}
        if 'ENTRY' not in own_writes:
            continue
        entry_response = own_writes['ENTRY'].get('response')
        if (t['state'] == 'REJECTED' and isinstance(entry_response, dict)
                and entry_response.get('success') is False):
            continue
        executed += 1
        p, owned, detail = t['plan'], t['owned'], t['detail']
        row = {'tradeId': tid, 'symbol': t['symbol'], 'journalState': t['state'],
               'journalUpdatedMs': t['updated'], 'auditStatus': 'INCOMPLETE',
               'fundingIncluded': False, 'strategyHistoryReplayable': False}
        result['trades'].append(row)
        if t['state'] == 'REVIEW_REQUIRED':
            finding(tid, 'RECONCILIATION_REQUIRED', 'ERROR',
                    {'symbol': t['symbol'], 'reason': detail.get('reason', 'UNSPECIFIED')},
                    'Verificare prove ordine/fill; non sbloccare il journal o ripetere ordini da questo audit.')
        try:
            side = p['entry']['positionSide']
            if side not in ('LONG', 'SHORT'):
                raise ValueError('INVALID_SIDE')
            long = side == 'LONG'
            amounts = owned or detail
            q = num(amounts['quantity'])
            entry = num(amounts['actualEntryCostUSDT'])
            entryfee = num(amounts['actualEntryFeesUSDT'])
            sizing = p['sizing']
            lev, requested = num(p['actualCrossLeverage']), num(p['requestedLeverage'])
            rate, target = num(p['exitFeeRate']), num(p['targetNetProfitUSDT'])
            tick, step = num(sizing['priceTick']), num(sizing['quantityStep'])
            if min(q, entry, lev, requested, target, tick, step) <= 0 or entryfee < 0 or not 0 <= rate < 1:
                raise ValueError('INVALID_ECONOMICS')
            row.update(side=side, quantity=str(q), entryNotional=str(entry), entryFee=str(entryfee),
                       entryAverage=str(entry/q), requestedLeverage=str(requested),
                       verifiedLeverage=str(lev), historicalTarget=str(target),
                       historicalExitFeeRate=str(rate), quantityStep=str(step), priceTick=str(tick))
            if lev != requested:
                finding(tid, 'LEVERAGE_MISMATCH', 'ERROR', {'requested': str(requested), 'observed': str(lev)},
                        'Verificare la leva storica di posizione rispetto al piano originale.')
            if q % step or q > num(p['entry']['quantity']):
                finding(tid, 'QUANTITY_MISMATCH', 'ERROR', {'filled': str(q), 'requested': p['entry']['quantity'], 'step': str(step)},
                        'Verificare quantità e unità contrattuali nei fill e nel piano storico.')
            if sizing.get('budgetMode') == 'COST_INCLUDING_ENTRY_FEE':
                budget = num(sizing['targetCostUSDT'])
                theoretical = entry/lev + entryfee
                preview = num(sizing['estimatedCostUSDT'])
                row.update(costBudget=str(budget), costPreview=str(preview),
                           costFromFillsTheoretical=str(theoretical),
                           costFillMinusPreview=str(theoretical-preview), actualWalletDebitVerified=False)
                if theoretical > budget + EPS:
                    finding(tid, 'COST_ABOVE_BUDGET', 'WARNING', {'budget': str(budget), 'theoreticalCostFromFills': str(theoretical)},
                            'Esaminare differenza preview/fill e margine effettivo; non modificare automaticamente il budget.')
                plannedq = num(p['entry']['quantity'])
                previewprice = num(sizing['notionalUSDT']) / num(sizing['quantity'])
                previewfee = num(sizing['entryFeeRate'])
                if not 0 <= previewfee < 1:
                    raise ValueError('INVALID_PREVIEW_FEE')
                calculated = plannedq*previewprice*(1/requested+previewfee)
                row['previewCostArithmeticValid'] = abs(calculated-preview) <= EPS
                if abs(calculated-preview) > EPS or preview > budget + EPS or plannedq % step:
                    finding(tid, 'SIZING_ARITHMETIC', 'ERROR', {'computedPreviewCost': str(calculated), 'recordedPreviewCost': str(preview)},
                            'Rivedere il calcolo Cost e l’arrotondamento quantità nel piano storico.')
            denom = q * (1-rate if long else 1+rate)
            be = (entry+entryfee if long else entry-entryfee)/denom
            raw = (entry+entryfee+target if long else entry-entryfee-target)/denom
            expected = (raw/tick).to_integral_value(rounding=ROUND_CEILING if long else ROUND_FLOOR)*tick
            if expected <= 0:
                raise ValueError('UNREACHABLE_TP')
            net_at = lambda price: (q*price-entry if long else entry-q*price)-entryfee-q*price*rate
            row.update(breakEvenPrice=str(be), expectedTP=str(expected), expectedNetAtTP=str(net_at(expected)))
            tp = owned.get('tpRequest', {})
            tp_id = _ack_id(own_writes.get('TP'))
            exit_ids = {str(detail['exitOrderId'])} if detail.get('exitOrderId') else set()
            if tp_id and own_writes['TP']['payload'] == tp:
                exit_ids.add(tp_id)
            if tp:
                trailing_exit=(p.get('exitPolicy') or {}).get('mode')=='trailing'
                if trailing_exit:
                    from weex_trailing import request_from_fixed_tp
                    fixed={'symbol':t['symbol'],'positionSide':side,'reduceOnly':True,
                           'quantity':str(q),'triggerPrice':str(expected),'clientAlgoId':p['tpClientId']}
                    expected_request=request_from_fixed_tp(fixed,p['exitPolicy'],tick)
                    activation=num(tp['activatePrice']);callback=num(tp['callbackRate'])
                    used=activation*(1-callback if long else 1+callback)
                    row.update(exitMode='TRAILING',activationPrice=str(activation),callbackRate=str(callback),
                               targetRole='TRAILING_ACTIVATION' if p['exitPolicy'].get('activationMode')=='AT_NET_TARGET' else 'NET_EXIT_TARGET')
                    price_valid=tp==expected_request
                else:
                    used = num(tp['triggerPrice']);price_valid=used==expected
                row.update(tpUsed=str(used), tpOwner='BOT', trigger=tp.get('workingType',tp.get('triggerPriceType')),
                           expectedNetAtUsedTP=str(net_at(used)), tpAcknowledged=tp_id is not None)
                if (not price_valid or num(tp['quantity']) != q or tp.get('positionSide') != side
                        or tp.get('symbol') != t['symbol'] or tp.get('reduceOnly') is not True):
                    finding(tid, 'BOT_TP_PARAMETERS', 'ERROR', {'expectedTP': str(expected), 'plannedTP': str(used)},
                            'Verificare parametri del TP attribuito al bot; l’audit non modifica ordini.')
            elif detail.get('externalTP'):
                external = proofs.get(tid, {}).get('exitOrder', {})
                if (str(external.get('orderId')) in exit_ids and external.get('symbol') == t['symbol']
                        and external.get('positionSide') == side and num(external.get('executedQty', 0)) == q):
                    used = num(external['stopPrice'])
                    row.update(tpUsed=str(used), tpOwner='EXTERNAL_USER', trigger=external.get('workingType'),
                               expectedNetAtUsedTP=str(net_at(used)))
                    if used != expected:
                        finding(tid, 'EXTERNAL_TP_DIFFERENT_FROM_TARGET', 'WARNING',
                                {'tpUsed': str(used), 'strategyTP': str(expected), 'netAtUsedTP': str(net_at(used))},
                                'Distinguere il TP esterno dal calcolo automatico; non attribuire questa scelta alla strategia.')
                else:
                    row['tpOwner'] = 'EXTERNAL_UNVERIFIED_LOCAL_PROOF'
            if not tp_id and int(t['created'])/1000 < now-120:
                finding(tid, 'BOT_TP_ACK_ABSENT', 'WARNING',
                        {'state': t['state'], 'externalTP': bool(detail.get('externalTP'))},
                        'Manca una conferma TP del bot nel registro. È una lacuna storica, non prova che una posizione sia ancora scoperta.')

            candidates = []
            for index, r in enumerate(report.get('rows', [])):
                if (r.get('symbol') == t['symbol'] and r.get('side') == side and r.get('fullCycle') is True
                        and len(r.get('orderIds', [])) == 1 and str(r['orderIds'][0]) in exit_ids
                        and num(r.get('quantity', 0)) == q):
                    candidates.append((index, r))
            r = None
            if len(candidates) == 1:
                index, r = candidates[0]
                matched_report_indices.add(index)
                row['sourceClosedAtMs'] = r.get('closedAt')
            elif len(candidates) > 1:
                finding(tid, 'AMBIGUOUS_CLOSED_REPORT', 'ERROR', {'matches': len(candidates)},
                        'Non scegliere una chiusura per somiglianza: verificare gli identificativi degli ordini.')

            if t['state'] == 'CLOSED' and all(k in detail for k in ('actualExitValueUSDT','actualExitFeesUSDT','realizedNetBeforeFundingUSDT')):
                exitvalue, exitfee = num(detail['actualExitValueUSDT']), num(detail['actualExitFeesUSDT'])
                row['exitEvidence'] = 'RECONCILED_LEDGER'
                row['auditStatus'] = 'ECONOMICS_CHECKED_FUNDING_EXCLUDED'
            elif r and all(r.get(k) is not None for k in ('pnl','fees','net','exit')):
                exitvalue = num(r['exit'])*q
                exitfee = num(r['fees'])-entryfee
                row['exitEvidence'] = 'AGGREGATE_REPORT_PROVISIONAL'
                row['auditStatus'] = 'PROVISIONAL_EXIT'
                finding(tid, 'EXIT_EVIDENCE_PROVISIONAL', 'WARNING', {'exitOrderIds': r['orderIds'], 'reportObservedAtMs': report.get('observedAtMs')},
                        'Conservare i fill e l’ordine d’uscita per riconciliare il risultato aggregato senza alterare il journal da questo audit.')
            else:
                row['exitEvidence'] = 'NOT_AVAILABLE'
                row['auditStatus'] = 'WAIT_EXIT_EVIDENCE'
                continue
            if exitvalue <= 0 or exitfee < 0:
                raise ValueError('INVALID_EXIT_ECONOMICS')
            gross = exitvalue-entry if long else entry-exitvalue
            net = gross-entryfee-exitfee
            row.update(exitNotional=str(exitvalue), exitFee=str(exitfee), exitAverage=str(exitvalue/q),
                       grossRealized=str(gross), netRealizedBeforeFunding=str(net),
                       targetDifference=str(net-target), targetMetBeforeFunding=net+EPS >= target)
            if row.get('tpUsed') is not None:
                row['executionDifferenceVersusTP'] = str(net-net_at(num(row['tpUsed'])))
            if t['state'] == 'CLOSED' and abs(net-num(detail['realizedNetBeforeFundingUSDT'])) > EPS:
                finding(tid, 'LEDGER_NET_ARITHMETIC', 'ERROR', {'computedNet': str(net), 'storedNet': detail['realizedNetBeforeFundingUSDT']},
                        'Verificare lordo e commissioni conteggiate una sola volta nel registro.')
            if r and (abs(gross-num(r['pnl'])) > EPS or (r.get('net') is not None and abs(net-num(r['net'])) > EPS)):
                finding(tid, 'REPORT_LEDGER_ECONOMICS_MISMATCH', 'ERROR', {'computedNet': str(net), 'reportNet': r.get('net')},
                        'Confrontare fill originali e fee: report e registro non concordano.')
            if net+EPS < target and row.get('targetRole')!='TRAILING_ACTIVATION':
                finding(tid, 'TARGET_NOT_REACHED', 'WARNING',
                        {'target': str(target), 'netBeforeFunding': str(net), 'tpOwner': row.get('tpOwner'),
                         'exitEvidence': row['exitEvidence']},
                        'Distinguere calcolo TP da prezzo eseguito e TP manuale; proporre eventuali correzioni senza applicarle automaticamente.')
        except (KeyError, ValueError, TypeError, ArithmeticError) as exc:
            row['auditStatus'] = 'INCOMPLETE'
            finding(tid, 'INCOMPLETE_EVIDENCE', 'WARNING', {'errorType': type(exc).__name__, 'state': t['state']},
                    'Acquisire le prove mancanti; non usare la configurazione attuale per ricostruire i parametri passati.')
    result['coverage']['executedJournalRows'] = executed
    result['coverage']['unattributedClosedReportRows'] = len(report.get('rows', []))-len(matched_report_indices)
    result['unattributedClosed'] = [{'symbol': r.get('symbol'), 'closedAt': r.get('closedAt'), 'orderIds': r.get('orderIds')}
                                    for i, r in enumerate(report.get('rows', [])) if i not in matched_report_indices]
    if any(f['severity'] == 'ERROR' for f in findings):
        result['status'] = 'ATTENTION'
    elif findings or any(t['auditStatus'] in ('INCOMPLETE', 'WAIT_EXIT_EVIDENCE', 'PROVISIONAL_EXIT') for t in result['trades']):
        result['status'] = 'PARTIAL'
    return result
