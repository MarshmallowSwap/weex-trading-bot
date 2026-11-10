from datetime import datetime, timezone
import copy
import os
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import Mock, patch

from weex_persistent_execution import Journal, OfflineExchange, verify_tp_close
from weex_execution_readonly import pages, collect, recover

ORDER = {'symbol': 'ETHUSDT', 'side': 'BUY', 'positionSide': 'LONG', 'type': 'MARKET',
         'quantity': '0.002', 'tpTriggerPrice': '2500', 'TpWorkingType': 'MARK_PRICE'}
MANUAL = [{'id': '99', 'symbol': 'IOSTUSDT', 'side': 'SHORT', 'size': '822500'}]


def snapshot(client):
    return {'complete': True, 'age_ms': 100,
        'orders': [{'orderId': '1', 'clientOrderId': client, 'symbol': 'ETHUSDT',
                    'side': 'BUY', 'positionSide': 'LONG', 'executedQty': '0.002', 'status': 'FILLED'}],
        'positions': MANUAL + [{'id': '123', 'symbol': 'ETHUSDT', 'side': 'LONG', 'size': '0.002'}],
        'trades': [{'id': '9', 'orderId': '1', 'symbol': 'ETHUSDT', 'side': 'BUY', 'positionSide': 'LONG', 'qty': '0.002'}],
        'tp_orders': [{'algoId': '42', 'symbol': 'ETHUSDT', 'side': 'SELL', 'positionSide': 'LONG',
                       'orderType': 'TAKE_PROFIT_MARKET', 'algoStatus': 'UNTRIGGERED', 'quantity': '0.002',
                       'triggerPrice': '2500', 'workingType': 'MARK_PRICE', 'reduceOnly': True}]}


class DurableExecutionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'journal.db'
        self.j = Journal(self.path, environment='SIMULATION')
        self.client = self.j.prepare('candle-1', ORDER, MANUAL, [])['client_id']

    def submit(self, fail=False):
        transport = OfflineExchange({'success': True, 'orderId': '1', 'clientOrderId': self.client}, fail=fail)
        self.j.simulate_submit_once(self.client, transport)
        return transport

    def protected(self):
        self.submit()
        self.assertEqual(self.j.observe(self.client, snapshot(self.client))['state'], 'TP_NOT_CONFIRMED')
        request = {'clientAlgoId': 'wxtp_' + self.client[6:], 'symbol': 'ETHUSDT', 'positionSide': 'LONG',
                   'side': 'SELL', 'type': 'TAKE_PROFIT_MARKET', 'quantity': '0.002',
                   'triggerPrice': '2500', 'reduceOnly': True}
        self.j.bind_simulated_tp(self.client, request=request,
            ack={'success': True, 'algoId': '42', 'clientAlgoId': request['clientAlgoId']})
        return self.j.observe(self.client, snapshot(self.client))

    def test_repeat_prepare_keeps_identity_and_single_event(self):
        again = Journal(self.path, environment='SIMULATION').prepare('candle-1', ORDER, MANUAL, [])
        self.assertEqual(again['client_id'], self.client)
        self.assertEqual(self.j.overview()['total'], 1)

    def test_changed_payload_for_same_signal_is_not_overwritten(self):
        with self.assertRaisesRegex(ValueError, 'IMMUTABLE'):
            self.j.prepare('candle-1', {**ORDER, 'quantity': '0.003'}, MANUAL, [])
        self.assertEqual(self.j.get(self.client)['payload']['quantity'], '0.002')

    def test_environments_cannot_mix(self):
        with self.assertRaisesRegex(PermissionError, 'ENVIRONMENT'):
            Journal(self.path, environment='READ_ONLY')

    def test_production_refuses_even_fixture_transport_before_dispatch(self):
        journal = Journal(Path(self.temp.name) / 'production.db')
        client = journal.prepare('s', ORDER, MANUAL, [])['client_id']
        exchange = OfflineExchange()
        with self.assertRaisesRegex(PermissionError, 'REAL_SUBMISSION_DISABLED'):
            journal.simulate_submit_once(client, exchange)
        self.assertEqual(exchange.calls, [])
        self.assertEqual(journal.get(client)['state'], 'PREPARED_BLOCKED')

    def test_arbitrary_sdk_or_callable_cannot_be_used_as_transport(self):
        writer = Mock()
        with self.assertRaises(PermissionError):
            self.j.simulate_submit_once(self.client, writer)
        writer.submit.assert_not_called()

    def test_manual_symbol_is_never_reserved(self):
        with self.assertRaisesRegex(ValueError, 'EXPOSURE'):
            self.j.prepare('manual', {**ORDER, 'symbol': 'IOSTUSDT'}, MANUAL, [])

    def test_blockers_prevent_simulated_submission(self):
        client = self.j.prepare('blocked', ORDER, MANUAL, ['LIQUIDITY_CHECK_FAILED'])['client_id']
        with self.assertRaisesRegex(PermissionError, 'BLOCKERS'):
            self.j.simulate_submit_once(client, OfflineExchange())

    def test_unknown_is_committed_before_dispatch_and_survives_crash(self):
        def crash(transport, order):
            fresh = Journal(self.path, environment='SIMULATION')
            self.assertEqual(fresh.get(self.client)['state'], 'SUBMISSION_UNKNOWN')
            raise KeyboardInterrupt('SIMULATED_PROCESS_CRASH')
        with patch.object(OfflineExchange, 'submit', crash), self.assertRaises(KeyboardInterrupt):
            self.submit()
        restarted = Journal(self.path, environment='SIMULATION')
        exchange = OfflineExchange()
        restarted.simulate_submit_once(self.client, exchange)
        self.assertEqual(exchange.calls, [])

    def test_subprocess_crash_after_commit_survives_real_process_restart(self):
        child = (
            "from weex_persistent_execution import Journal, OfflineExchange; "
            "import os,sys; "
            "OfflineExchange.submit=lambda self,order: os._exit(77); "
            "j=Journal(sys.argv[1],environment='SIMULATION'); "
            "c=j.prepare('subprocess-crash',"
            "{'symbol':'ETHUSDT','side':'BUY','positionSide':'LONG','type':'MARKET',"
            "'quantity':'0.002','tpTriggerPrice':'2500'},[],[])['client_id']; "
            "j.simulate_submit_once(c,OfflineExchange())"
        )
        crash_path = Path(self.temp.name) / 'subprocess-crash.db'
        result = subprocess.run(
            [sys.executable, '-c', child, str(crash_path)],
            cwd=str(Path(__file__).resolve().parent),
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 77, result.stderr)
        restarted = Journal(crash_path, environment='SIMULATION')
        client = restarted.clients()[0]
        self.assertEqual(restarted.get(client)['state'], 'SUBMISSION_UNKNOWN')
        transport = OfflineExchange()
        restarted.simulate_submit_once(client, transport)
        self.assertEqual(transport.calls, [])
        self.assertEqual(restarted.get(client)['state'], 'SUBMISSION_UNKNOWN')

    def test_concurrent_workers_dispatch_at_most_once(self):
        transport = OfflineExchange({'success': True, 'orderId': '1', 'clientOrderId': self.client})
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(lambda _: self.j.simulate_submit_once(self.client, transport), range(8)))
        self.assertEqual(len(transport.calls), 1)

    def test_timeout_does_not_authorize_retry(self):
        transport = self.submit(fail=True)
        self.j.simulate_submit_once(self.client, transport)
        self.assertEqual(len(transport.calls), 1)
        self.assertEqual(self.j.get(self.client)['state'], 'SUBMISSION_UNKNOWN')

    def test_lost_ack_recovers_only_from_matching_order_and_fills(self):
        self.submit(fail=True)
        self.assertEqual(self.j.observe(self.client, snapshot(self.client))['state'], 'TP_NOT_CONFIRMED')
        self.assertFalse(self.j.get(self.client)['canSubmit'])

    def test_partial_fill_and_manual_size_addition_remain_unresolved(self):
        self.submit()
        for mutate in ('partial', 'manual'):
            data = snapshot(self.client)
            if mutate == 'partial':
                data['orders'][0].update(status='PARTIALLY_FILLED', executedQty='0.001')
            else:
                data['positions'][-1]['size'] = '0.003'
            self.assertEqual(self.j.observe(self.client, data)['state'], 'RECONCILIATION_REQUIRED')

    def test_rejection_conflict_remains_unresolved_on_repeated_reads(self):
        self.j.simulate_submit_once(self.client, OfflineExchange({'success': False}))
        for _ in range(2):
            self.assertEqual(self.j.observe(self.client, snapshot(self.client))['reason'], 'REJECTION_CONTRADICTS_ORDER')

    def test_malformed_ack_fails_closed(self):
        self.j.simulate_submit_once(self.client, OfflineExchange('unexpected'))
        self.assertEqual(self.j.observe(self.client, {'orders': []})['state'], 'UNKNOWN_EXECUTION')

    def test_unsubmitted_preview_cannot_become_owned_from_external_match(self):
        self.assertEqual(self.j.observe(self.client, snapshot(self.client))['reason'], 'NEVER_DISPATCHED')

    def test_tp_binding_persists_across_restart(self):
        self.assertEqual(self.protected()['state'], 'OPEN_WITH_MATCHED_TP')
        restarted = Journal(self.path, environment='SIMULATION')
        result = restarted.observe(self.client, snapshot(self.client))
        self.assertEqual(result['tpId'], '42')
        self.assertFalse(result['canClose'])

    def test_close_needs_bound_tp_and_exit_fills_not_disappearance(self):
        self.protected()
        data = dict(algo={'algoId': '42', 'algoStatus': 'FILLED', 'actualOrderId': '2',
                         'symbol': 'ETHUSDT', 'positionSide': 'LONG', 'side': 'SELL',
                         'orderType': 'TAKE_PROFIT_MARKET', 'reduceOnly': True,
                         'quantity': '0.002', 'triggerPrice': '2500'},
                    exit_order={'orderId': '2', 'symbol': 'ETHUSDT', 'side': 'SELL', 'positionSide': 'LONG',
                                'reduceOnly': True, 'status': 'FILLED', 'executedQty': '0.002'},
                    trades=[{'id': '10', 'orderId': '2', 'symbol': 'ETHUSDT', 'side': 'SELL',
                             'positionSide': 'LONG', 'qty': '0.002'}], positions=MANUAL, complete=True, age_ms=100)
        for field, value in (('trades', []), ('complete', False), ('age_ms', 6000)):
            bad = {**data, field: value}
            self.assertEqual(self.j.observe_close(self.client, **bad)['state'], 'CLOSE_RECONCILIATION_REQUIRED')
        bad = copy.deepcopy(data); bad['algo']['actualOrderId'] = 'other'
        self.assertEqual(self.j.observe_close(self.client, **bad)['state'], 'CLOSE_RECONCILIATION_REQUIRED')
        result = self.j.observe_close(self.client, **data)
        self.assertEqual(result['state'], 'CLOSED_BY_MATCHED_TP')
        self.assertEqual(Journal(self.path, environment='SIMULATION').get(self.client)['state'], 'CLOSED_BY_MATCHED_TP')
        self.assertEqual(self.j.observe(self.client, snapshot(self.client))['state'], 'CLOSED_BY_MATCHED_TP')


class RunnerIntegrationTests(unittest.TestCase):
    def run_cycles(self, conditional):
        import weex_simple_bot as runner
        import json
        from test_weex_pretrade_regression import MARKET, META, CFG, ACCOUNT
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            (root/'weex_ai_risk_config.json').write_text(json.dumps(CFG), encoding='utf-8')
            calls=[]
            def reader(client, op, **query):
                calls.append(op)
                return {'get_capi_v3_openOrders': [], 'get_capi_v3_openAlgoOrders': conditional,
                        'get_capi_v3_account_position_allPosition': MANUAL,
                        'get_capi_v3_account_accountConfig': {'canTrade': True},
                        'get_capi_v3_account_balance': [{'asset': 'USDT','availableBalance': '100'}],
                        'get_capi_v3_account_symbolConfig': [ACCOUNT],
                        'get_capi_v3_account_commissionRate': {'symbol':'ETHUSDT','takerCommissionRate':'0.001'}}[op]
            def public(path, **query):
                return {'symbols':[META]} if path.endswith('exchangeInfo') else [{'symbol':'ETHUSDT','brackets':[
                    {'notionalFloor':'0','notionalCap':'10000','initialLeverage':400}]}]
            with patch.object(runner,'R',root),patch.object(runner,'DB',root/'decisions.db'),\
                 patch.object(runner,'scan',return_value={'asOf':datetime.now(timezone.utc).isoformat(),'results':[MARKET]}),\
                 patch.object(runner,'make_client',return_value=object()),\
                 patch.object(runner,'read',side_effect=reader),patch.object(runner,'public',side_effect=public):
                first=runner.run();second=runner.run()
            self.assertTrue(all(op.startswith('get_') for op in calls))
            return first,second

    def test_runner_registers_once_across_repeated_cycles(self):
        first,second=self.run_cycles([])
        self.assertEqual(first['executionJournal']['total'],1)
        self.assertEqual(second['executionJournal']['total'],1)
        self.assertEqual(first['results'][0]['persistentIntent'],second['results'][0]['persistentIntent'])
        self.assertFalse(second['ordersSubmitted'])
        self.assertEqual(second['restartRecovery']['checkedIntents'],1)

    def test_existing_conditional_order_blocks_symbol(self):
        first,_=self.run_cycles([{'symbol':'ETHUSDT','algoId':'123'}])
        self.assertIn('SYMBOL_OCCUPIED',first['results'][0]['reasons'])
        self.assertNotIn('plan',first['results'][0])
        self.assertEqual(first['executionJournal']['total'],0)


class CollectorTests(unittest.TestCase):
    def item(self):
        return {'client_id': 'wxsim_test', 'symbol': 'ETHUSDT', 'ack': {'success': True, 'orderId': '1'}}

    def reader(self, operation, **query):
        data = snapshot('wxsim_test')
        return {'get_capi_v3_openOrders': [], 'get_capi_v3_order': data['orders'][0],
                'get_capi_v3_order_history': data['orders'], 'get_capi_v3_userTrades': data['trades'],
                'get_capi_v3_openAlgoOrders': data['tp_orders'],
                'get_capi_v3_account_position_allPosition': data['positions']}[operation]

    def test_collector_uses_only_gets_and_conditional_page_one(self):
        reader = Mock(side_effect=self.reader)
        result = collect(reader, self.item())
        self.assertTrue(result['complete'])
        for call in reader.call_args_list:
            self.assertTrue(call.args[0].startswith('get_'))
            if call.args[0] == 'get_capi_v3_openAlgoOrders':
                self.assertEqual(call.kwargs['page'], 1)

    def test_no_order_found_never_allows_retry(self):
        item = self.item(); item['ack'] = None
        result = collect(lambda operation, **kw: [], item)
        self.assertFalse(result['complete']); self.assertFalse(result['canRetry'])

    def test_full_fill_page_is_incomplete(self):
        def reader(op, **kw):
            return snapshot('wxsim_test')['trades']*100 if op == 'get_capi_v3_userTrades' else self.reader(op, **kw)
        self.assertFalse(collect(reader, self.item())['complete'])

    def test_repeated_pages_rejected(self):
        batch = [{'algoId': n + 1, 'symbol': 'ETHUSDT'} for n in range(100)]
        with self.assertRaisesRegex(ValueError, 'REPEATED'):
            pages(lambda *a, **k: batch, 'get_capi_v3_openAlgoOrders', identity='algoId', start=1)

    def test_slow_collection_is_not_fresh(self):
        with patch('weex_execution_readonly.time.monotonic', side_effect=[0, 6]):
            self.assertFalse(collect(self.reader, self.item())['complete'])

    def test_previews_require_no_recovery_network_calls(self):
        with tempfile.TemporaryDirectory() as folder:
            journal = Journal(Path(folder)/'journal.db')
            client = journal.prepare('preview', ORDER, MANUAL, ['STOP_BEFORE_SUBMISSION'])['client_id']
            reader = Mock()
            self.assertEqual(recover(journal, reader, [])['checkedIntents'], 1)
            reader.assert_not_called()
            result = recover(journal, reader, [{'clientOrderId': client}])
            self.assertEqual(result['observations'][0]['state'], 'UNEXPECTED_EXCHANGE_ORDER')


if __name__ == '__main__':
    unittest.main()
