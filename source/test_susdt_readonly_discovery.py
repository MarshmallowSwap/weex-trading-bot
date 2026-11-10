import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
from demo_universe_discovery import classify
from weex_susdt_readonly import SusdtReadOnlyClient

class DiscoveryTests(unittest.TestCase):
    def test_real_pairs_with_s_ending_not_demo(self):
        rows = [{'symbol':s, 'quoteAsset':'USDT', 'marginAsset':'USDT'} for s in ('AXSUSDT','SUSDT','WAVESUSDT')]
        result = classify({'symbols':rows},[])
        self.assertEqual(result['count'],0)
        self.assertEqual(len(result['rejectedSuffixMatches']),3)
    def test_explicit_collateral_required(self):
        rows=[{'symbol':'BTCSUSDT','quoteAsset':'SUSDT','marginAsset':'USDT'},
              {'symbol':'ETHSUSDT','quoteAsset':'SUSDT','marginAsset':'SUSDT'}]
        result=classify({'symbols':rows},[])
        self.assertEqual([r['symbol'] for r in result['demoPairs']],['ETHSUSDT'])
        self.assertFalse(result['orderEligibilityVerified'])
    def test_position_is_not_contract_metadata(self):
        result=classify({'symbols':[]},[{'symbol':'BTCSUSDT','asset':'SUSDT','leverage':'100'}])
        self.assertEqual(result['positionObservedSymbols'],['BTCSUSDT'])
        self.assertEqual(result['count'],0)
    def test_absent_assets_not_guessed(self):
        self.assertEqual(classify({'symbols':[{'symbol':'BTCSUSDT'}]},[])['count'],0)
    def test_bad_schema_fails(self):
        with self.assertRaises(ValueError):classify({'code':-1},[])

class TransportTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        path=Path(self.temp.name)/'dummy.json'
        path.write_text(json.dumps({'api_key':'DUMMY','secret_key':'DUMMY','passphrase':'DUMMY'}))
        self.session=Mock()
        self.session.request.return_value.status_code=200
        self.session.request.return_value.json.return_value=[]
        self.client=SusdtReadOnlyClient(path,self.session)
    def test_only_demo_reads_signed(self):
        self.client.get('/capi/v3/sim/order/history',symbol='BTCSUSDT',limit=100,page=0)
        call=self.session.request.call_args.kwargs
        self.assertEqual(call['method'],'GET')
        self.assertEqual(call['url'],'https://api-contract.weex.com/capi/v3/sim/order/history?limit=100&page=0&symbol=BTCSUSDT')
        self.assertFalse(call['allow_redirects'])
        self.assertEqual(call['headers']['ACCESS-KEY'],'DUMMY')
    def test_public_reads_never_receive_credentials(self):
        self.client.get('/capi/v3/market/exchangeInfo')
        self.assertEqual(self.session.request.call_args.kwargs['headers'],{})
    def test_mutation_and_real_private_routes_rejected(self):
        for path in ('/capi/v3/sim/order','/capi/v3/closePositions','/capi/v3/account/balance',
                     'https://api-sim.weex.com/capi/v3/sim/balance','/capi/v3/sim/balance?x=1'):
            with self.subTest(path=path),self.assertRaises(PermissionError):self.client.get(path)
        self.session.request.assert_not_called()
    def test_redirect_no_followup(self):
        self.session.request.return_value.status_code=302
        with self.assertRaises(PermissionError):self.client.get('/capi/v3/sim/balance')
        self.assertEqual(self.session.request.call_count,1)
    def test_error_not_interpreted_as_empty_balance(self):
        self.session.request.return_value.json.return_value={'code':-1121}
        with self.assertRaises(RuntimeError):self.client.get('/capi/v3/sim/balance')
    def test_timeout_no_fallback(self):
        self.session.request.side_effect=TimeoutError()
        with self.assertRaises(TimeoutError):self.client.get('/capi/v3/sim/balance')
        self.assertEqual(self.session.request.call_count,1)
    def test_unknown_parameter_blocked(self):
        with self.assertRaises(PermissionError):self.client.get('/capi/v3/sim/balance',body='order')
        self.session.request.assert_not_called()

if __name__=='__main__':unittest.main()
