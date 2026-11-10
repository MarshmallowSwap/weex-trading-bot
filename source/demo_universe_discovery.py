"""Discover SUSDT collateral explicitly; symbol suffixes are not asset evidence."""
import json
from pathlib import Path
from datetime import datetime, timezone
from weex_susdt_readonly import SusdtReadOnlyClient

def classify(metadata, positions):
    if not isinstance(metadata, dict) or not isinstance(metadata.get('symbols'), list):
        raise ValueError('INVALID_EXCHANGE_METADATA')
    if not isinstance(positions, list):
        raise ValueError('INVALID_DEMO_POSITIONS')
    verified, rejected = [], []
    for row in metadata['symbols']:
        symbol = row.get('symbol')
        if row.get('marginAsset') == 'SUSDT' and row.get('quoteAsset') == 'SUSDT':
            verified.append({k: row.get(k) for k in ('symbol', 'quoteAsset', 'marginAsset', 'maxLeverage',
                                                     'contractVal', 'minOrderSize', 'quantityPrecision', 'pricePrecision')})
        elif isinstance(symbol, str) and symbol.endswith('SUSDT'):
            rejected.append({'symbol': symbol, 'quoteAsset': row.get('quoteAsset'),
                             'marginAsset': row.get('marginAsset'), 'reason': 'NO_EXPLICIT_SUSDT_COLLATERAL'})
    observed = sorted({p['symbol'] for p in positions if p.get('asset') == 'SUSDT' and isinstance(p.get('symbol'), str)})
    return {'demoPairs': verified, 'count': len(verified), 'positionObservedSymbols': observed,
            'rejectedSuffixMatches': rejected,
            'documentedExampleSymbols': ['BTCSUSDT'],
            'orderEligibilityVerified': False, 'ordersSent': False}

def run(root=None):
    root = Path(root or Path(__file__).parent)
    client = SusdtReadOnlyClient(root/'weex_credentials.json')
    try:
        metadata = client.get('/capi/v3/market/exchangeInfo')
        try:
            positions = client.get('/capi/v3/sim/position/allPosition')
            if not isinstance(positions, list): raise ValueError('INVALID_POSITION_SCHEMA')
            position_check = {'ok': True, 'count': len(positions)}
        except Exception as exc:
            positions = []
            position_check = {'ok': False, 'reason': type(exc).__name__}
        result = classify(metadata, positions)
        result.update(checkedAt=datetime.now(timezone.utc).isoformat(),
                      source='Exact quoteAsset/marginAsset SUSDT; no suffix inference', simPositions=position_check)
        path = root/'demo_universe_discovery_latest.json'
        temp = path.with_suffix('.tmp')
        temp.write_text(json.dumps(result, indent=2), encoding='utf-8')
        temp.replace(path)
        return result
    finally:
        client.close()

if __name__ == '__main__':
    report = run()
    print(json.dumps({'demoMetadataCount': report['count'],
                      'rejectedSuffixMatches': len(report['rejectedSuffixMatches']),
                      'simPositions': report['simPositions'], 'ordersSent': False}))
