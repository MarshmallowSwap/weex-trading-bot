"""Validate a fresh visible WEEX SUSDT demo book. No network or order operations.

The caller supplies a full accessibility observation taken through the browser.
This does not certify the public API book or enable automatic execution.
"""
import hashlib,json,re
from datetime import datetime,timezone
from decimal import Decimal as D
from urllib.parse import urlsplit

def display_decimal(text):
    if not re.fullmatch(r'(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d+)?',text):
        raise ValueError('INVALID_VISIBLE_NUMBER')
    return D(text.replace(',',''))

def number_lower_bound(text):
    match=re.fullmatch(r'((?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d+)?)([KM]?)',text)
    if not match:raise ValueError('INVALID_VISIBLE_NUMBER')
    value,suffix=match.groups();scale={'':D(1),'K':D(1000),'M':D(1000000)}[suffix]
    precision=len(value.split('.')[1]) if '.' in value else 0
    # One displayed increment covers truncation or rounding in either direction.
    lower=max(D(0),display_decimal(value)*scale-D(10)**(-precision)*scale)
    return display_decimal(value)*scale,lower

def inspect_snapshot(snapshot,base_asset,*,now_ms=None):
    if not re.fullmatch('[A-Z0-9]+',base_asset):raise ValueError('INVALID_ASSET')
    symbol=base_asset+'SUSDT'
    url=urlsplit(snapshot['url'])
    if (url.scheme!='https' or url.netloc!='www.weex.com' or url.query or url.fragment
        or url.path!='/futures/demo-trading/'+base_asset+'-SUSDT'):
        raise ValueError('NOT_EXPECTED_DEMO_MARKET')
    now_ms=now_ms if now_ms is not None else datetime.now(timezone.utc).timestamp()*1000
    start=snapshot['captureStartedAtMs'];end=snapshot['observedAtMs']
    if not all(type(x) in (int,float) for x in (start,end,now_ms)):
        raise ValueError('INVALID_CAPTURE_TIME')
    if not (0<=end-start<=5000 and end<=now_ms and 0<=now_ms-start<=30000):raise ValueError('STALE_OR_INVALID_CAPTURE')
    ax=snapshot['ax']
    if not isinstance(ax,str) or not re.search(r'heading '+re.escape(symbol)+r' Perp Demo,',ax):
        raise ValueError('DEMO_HEADING_MISMATCH')
    section=ax.split('container depth-list-container')
    if len(section)!=2:raise ValueError('MISSING_OR_AMBIGUOUS_BOOK')
    section=section[1].split('container depth-list-vs')[0]
    header=section.split('container depth-list-header')
    if len(header)!=2:raise ValueError('BOOK_HEADER_MISSING')
    header=header[1].split('container ask-contract-')[0]
    if not re.search(r'text Price\s+\d+ container\s+\d+ text \( SUSDT \)',header):
        raise ValueError('PRICE_UNIT_NOT_SUSDT')
    if not re.search(r'text Amount\s+\d+ text \(SUSDT\)\s+\d+ text Sum\s+\d+ text \(SUSDT\)',header):
        raise ValueError('AMOUNT_UNIT_NOT_SUSDT')
    pattern=r'container (ask|bid)-contract-(\d+)\s+\d+ text ([^\r\n]+)\s+\d+ text ([^\r\n]+)\s+\d+ text ([^\r\n]+)'
    rows={'ask':[],'bid':[]}
    for side,index,price,amount,total in re.findall(pattern,section):
        p=display_decimal(price.strip())
        display,lower=number_lower_bound(amount.strip())
        if not p.is_finite() or p<=0 or display<=0:raise ValueError('INVALID_BOOK_LEVEL')
        rows[side].append((int(index),p,lower))
    if [r[0] for r in rows['ask']]!=list(range(10,25)) or [r[0] for r in rows['bid']]!=list(range(15)):
        raise ValueError('INCOMPLETE_VISIBLE_TOP15')
    for side in rows:
        prices=[r[1] for r in rows[side]]
        if len(set(prices))!=15 or prices!=sorted(prices,reverse=True):
            raise ValueError('INVALID_VISIBLE_BOOK_ORDER')
    bid=rows['bid'][0][1];ask=rows['ask'][-1][1]
    if ask<=bid:raise ValueError('CROSSED_BOOK')
    spread=(ask-bid)/((ask+bid)/2)*10000
    depths={side:sum((r[2] for r in values),D(0)) for side,values in rows.items()}
    veto=[]
    if spread>15:veto.append('SPREAD_TOO_WIDE')
    if min(depths.values())<1000:veto.append('INSUFFICIENT_BOOK_DEPTH')
    return {'symbol':symbol,'environment':'WEEX_WEBSITE_SUSDT_DEMO','source':snapshot['url'],
            'observedAtMs':end,'expiresAtMs':start+30000,'snapshotSha256':hashlib.sha256(ax.encode()).hexdigest(),
            'amountUnit':'SUSDT','amountMeaning':'visible_quote_notional',
            'formula':'sum of displayed Amount(SUSDT), minus one display increment per level',
            'priceOrContractMultiplierApplied':False,'top15BidNotionalLowerBound':str(depths['bid']),
            'top15AskNotionalLowerBound':str(depths['ask']),'bestBid':str(bid),'bestAsk':str(ask),
            'spreadBps':float(spread),'passed':not veto,'vetoReasons':veto,
            'apiUnitCertification':False,'orderPermitted':False}

def assess(snapshot,base_asset,market,*,now_ms=None):
    now_ms=now_ms if now_ms is not None else datetime.now(timezone.utc).timestamp()*1000
    book=inspect_snapshot(snapshot,base_asset,now_ms=now_ms)
    if market.get('symbol')!=base_asset+'USDT':raise ValueError('SIGNAL_SYMBOL_MISMATCH')
    timestamp=datetime.fromisoformat(market['checkedAt'])
    if timestamp.tzinfo is None or not 0<=now_ms-timestamp.timestamp()*1000<=60000:
        raise ValueError('SIGNAL_STALE')
    # Explicitly use the analytical signal, not the public API liquidity result.
    # That separate API result remains unchanged in the source report.
    signal=market.get('marketSignal',market.get('decision'))
    reasons=list(book['vetoReasons'])
    if signal not in ('LONG','SHORT'):reasons.append('NO_CONFIRMED_SIGNAL')
    if market.get('momentum',{}).get('confirmed') is not True:reasons.append('MOMENTUM_NOT_CONFIRMED')
    if market.get('trend',{}).get('aligned') is not True:reasons.append('TRENDS_NOT_ALIGNED')
    return {'demoOrderBook':book,'signalSource':'Public USDT candles used by the configured strategy; not demo candles',
            'publicMarketSignal':signal,'marketEligibility':'WAIT' if reasons else 'DEMO_MARKET_CANDIDATE',
            'reasons':reasons,'orderPermitted':False,'ordersSubmitted':False,
            'remainingExecutionChecks':['Fresh demo account capacity','Maximum available demo leverage >=75',
                'Cost field 5 SUSDT including entry fee','Fill and TP reconciliation: +10 SUSDT beyond break-even; SL off'],
            'automationStatus':'Read-only snapshot adapter; browser acquisition is supervised, not an unattended bot feed'}
