"""Fixed-host, GET-only access to the SUSDT demo and public contract metadata."""
import base64
import hashlib
import hmac
import json
import time
from pathlib import Path
from urllib.parse import urlencode

BASE = 'https://api-contract.weex.com'
PRIVATE = frozenset(('/capi/v3/sim/balance', '/capi/v3/sim/position/allPosition', '/capi/v3/sim/order/history'))
PUBLIC = frozenset(('/capi/v3/market/exchangeInfo', '/capi/v3/market/apiTradingSymbols',
                    '/capi/v3/market/riskLimits', '/capi/v3/market/ticker/bookTicker'))

class SusdtReadOnlyClient:
    def __init__(self, credentials_path=None, session=None):
        import requests
        self.credentials_path = Path(credentials_path or Path(__file__).parent/'weex_credentials.json')
        self.session = session if session is not None else requests.Session()

    def get(self, path, **params):
        if path not in PRIVATE | PUBLIC:
            raise PermissionError('SUSDT_READ_PATH_NOT_ALLOWED')
        allowed = {'symbol', 'limit', 'page', 'startTime', 'endTime'} if path.endswith('/order/history') else {'symbol'}
        if path in ('/capi/v3/sim/balance', '/capi/v3/sim/position/allPosition', '/capi/v3/market/apiTradingSymbols'):
            allowed = set()
        if set(params) - allowed:
            raise PermissionError('UNSUPPORTED_READ_PARAMETERS')
        # No symbol rewriting and no switching to another host after an error.
        query = urlencode(sorted(params.items()))
        request_path = path + ('?' + query if query else '')
        headers = {}
        if path in PRIVATE:
            credentials = json.loads(self.credentials_path.read_text(encoding='utf-8'))
            timestamp = str(int(time.time()*1000))
            signature = base64.b64encode(hmac.new(credentials['secret_key'].encode(),
                (timestamp+'GET'+request_path).encode(), hashlib.sha256).digest()).decode()
            headers = {'ACCESS-KEY': credentials['api_key'], 'ACCESS-SIGN': signature,
                       'ACCESS-PASSPHRASE': credentials['passphrase'], 'ACCESS-TIMESTAMP': timestamp}
        response = self.session.request(method='GET', url=BASE+request_path, headers=headers,
                                        timeout=10, allow_redirects=False)
        if 300 <= response.status_code < 400:
            raise PermissionError('SUSDT_REDIRECT_BLOCKED')
        if response.status_code != 200:
            raise RuntimeError('SUSDT_READ_HTTP_'+str(response.status_code))
        result = response.json()
        if isinstance(result, dict) and ('code' in result or 'errorCode' in result or result.get('success') is False):
            # Return no raw response or exception containing signed headers.
            raise RuntimeError('SUSDT_READ_API_ERROR')
        return result

    def close(self):
        self.session.close()
