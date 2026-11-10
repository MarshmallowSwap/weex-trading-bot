import json
import unittest
from unittest.mock import Mock,patch

from weex_http_guard import HttpReadOnlySession, prepare_sdk_order, sdk_types

ORDER={'symbol':'ETHUSDT','side':'BUY','positionSide':'LONG','type':'MARKET','quantity':'0.002',
       'newClientOrderId':'wxpreview_offline','tpTriggerPrice':'2500','TpWorkingType':'MARK_PRICE'}


class TransportTests(unittest.TestCase):
    def setUp(self):
        self.network=Mock()
        self.network.request.return_value=Mock(status_code=200,headers={},text='[]')
        patcher=patch('requests.Session',return_value=self.network)
        patcher.start(); self.addCleanup(patcher.stop)
        budget_patcher=patch('weex_api_budget.request',
            side_effect=lambda session,method,url,**kw:session.request(method=method,url=url,**kw))
        budget_patcher.start(); self.addCleanup(budget_patcher.stop)
        self.guard=HttpReadOnlySession()

    def test_mutating_methods_block_before_network(self):
        for method in ('POST','DELETE','PUT','PATCH','post'):
            with self.subTest(method=method),self.assertRaisesRegex(PermissionError,'WRITE_DISABLED'):
                self.guard.request(method,'https://api-contract.weex.com/capi/v3/order')
        self.network.request.assert_not_called()

    def test_foreign_hosts_ports_credentials_and_unknown_paths_block(self):
        for url in ('http://api-contract.weex.com/capi/v3/order',
                    'https://api-contract.weex.com.attacker.test/capi/v3/order',
                    'https://user:pass@api-contract.weex.com/capi/v3/order',
                    'https://api-contract.weex.com:444/capi/v3/order',
                    'https://api-contract.weex.com/not-a-read-operation',
                    'https://api-contract.weex.com/capi/v3/order#unexpected'):
            with self.subTest(url=url),self.assertRaises(PermissionError):
                self.guard.request('GET',url)
        self.network.request.assert_not_called()

    def test_get_body_cannot_smuggle_write_payload(self):
        with self.assertRaises(PermissionError):
            self.guard.request('GET','https://api-contract.weex.com/capi/v3/order',data=b'order')
        self.network.request.assert_not_called()

    def test_documented_read_passes_with_redirects_disabled(self):
        self.guard.request('GET','https://api-contract.weex.com/capi/v3/order?orderId=123',allow_redirects=True)
        self.assertFalse(self.network.request.call_args.kwargs['allow_redirects'])

    def test_redirect_response_not_followed_or_treated_as_success(self):
        self.network.request.return_value.status_code=302
        with self.assertRaisesRegex(PermissionError,'REDIRECT_DISABLED'):
            self.guard.request('GET','https://api-contract.weex.com/capi/v3/account/balance')
        self.network.request.assert_called_once()

    def test_direct_official_sdk_write_cannot_bypass_guard(self):
        config,contract,_=sdk_types()
        sdk=contract(config_rest_api=config(base_path='https://api-contract.weex.com',
            api_key='DUMMY',api_secret='DUMMY',passphrase='DUMMY',session=self.guard,max_retries=0))
        with self.assertRaisesRegex(PermissionError,'HTTP_WRITE_DISABLED'):
            sdk.rest_api.execute_operation('post_capi_v3_order',ORDER)
        self.network.request.assert_not_called()

    def test_sdk_preview_never_constructs_network_session(self):
        with patch('requests.Session',side_effect=AssertionError('NO_NETWORK_SESSION')):
            result=prepare_sdk_order(ORDER)
        self.assertEqual(result['state'],'STOPPED_BEFORE_NETWORK')
        self.assertEqual(result['networkRequests'],0)
        self.assertFalse(result['exchangeAccepted'])
        self.assertFalse(result['ordersSubmitted'])

    def test_sdk_payload_digest_is_stable_and_changes_with_quantity(self):
        first=prepare_sdk_order(ORDER)
        self.assertEqual(first,prepare_sdk_order(ORDER))
        self.assertNotEqual(first['payloadSha256'],prepare_sdk_order({**ORDER,'quantity':'0.003'})['payloadSha256'])

    def test_ignored_unknown_payload_fields_do_not_pass_as_verified(self):
        with self.assertRaises(ValueError):
            prepare_sdk_order({**ORDER,'unsupportedField':'should_not_disappear'})

    def test_returned_preview_contains_no_auth_headers(self):
        result=json.dumps(prepare_sdk_order(ORDER))
        self.assertNotIn('ACCESS-',result)
        self.assertNotIn('OFFLINE_ONLY',result)


if __name__=='__main__': unittest.main()
