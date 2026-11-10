"""Consolidated WEEX 1000-fill accounting proof, strictly offline.

Confirms 1000 individually valid fills, 137 fully traced exchange orders,
132 filled-order quantity/economic matches plus 5 canceled partial fills.
Separately flags the parent cumQuote conflict (including FILLED orders).
Never asserts full account history or enables LIVE.
"""
import json,os
from pathlib import Path
from decimal import Decimal as D
from datetime import datetime,timezone
from collections import Counter
ROOT=Path(__file__).resolve().parent
def read(name):return json.loads((ROOT/name).read_text(encoding='utf-8'))
def run():
 snapshot=read('weex_trade_1000_snapshot.json')
 identities=read('weex_trade_1000_reconciliation_latest.json')
 arithmetic=read('weex_trade_1000_fill_arithmetic_latest.json')
 orders=read('weex_trade_1000_economics_checkpoint.json')['orders']
 partial=read('weex_trade_1000_partial_canceled_audit.json')
 details=partial['details']
 fills=snapshot['trades']
 assert len(fills)==1000 and len({str(x['id']) for x in fills})==1000
 assert identities['all1000TradeOrderIdsVerified'] is True and identities['matchedTrades']==1000
 assert len(orders)==137 and len(details)==5
 assert len({x['orderId'] for x in details})==5
 assert arithmetic['arithmeticVerifiedFills']==1000 and arithmetic['invalidFills']==0
 parents={str(x['orderId']) for x in fills}
 assert parents==set(orders)
 verified={k:x for k,x in orders.items() if x['verified'] is True}
 canceled={x['orderId']:x for x in details}
 assert len(verified)==132 and len(canceled)==5 and not (set(verified)&set(canceled))
 assert all(x['partialFillQuantityVerified'] for x in details)
 matched_parent=sum(x['cumQuoteEqualFill'] is True for x in verified.values())
 discrepant_filled=sum(x['cumQuoteEqualFill'] is False for x in verified.values())
 assert matched_parent+discrepant_filled==132
 parent_conflicts=discrepant_filled+sum(not x['parentQuoteMatches'] for x in details)
 by_order=Counter(str(x['orderId']) for x in fills)
 assert all(1<=v<100 for v in by_order.values())
 assert all(int(x['fillCount'])==by_order[oid] for oid,x in verified.items())
 assert all(x['fillCount']==by_order[oid] for oid,x in canceled.items())
 fills_quote=D(arithmetic['internalFillNotionalUSDT'])
 fills_fees=D(arithmetic['internalFeesUSDT'])
 cert_quote=sum((D(x['notionalUSDT']) for x in verified.values()),D(0))
 cert_fees=sum((D(x['feesUSDT']) for x in verified.values()),D(0))
 partial_quote=sum((D(x['fillNotionalUSDT']) for x in details),D(0))
 partial_fees=sum((D(x['feesUSDT']) for x in details),D(0))
 assert cert_quote+partial_quote==fills_quote
 assert cert_fees+partial_fees==fills_fees
 report={'checkedAt':datetime.now(timezone.utc).isoformat(),
   'scope':'EXACT_FIXED_1000_AUTHENTICATED_WEEX_FILL_SNAPSHOT',
   'snapshotAt':snapshot['checkedAt'],
   'fillsIndividuallyVerified':1000,'fillsLinkedToOrders':1000,
   'ordersWithExactExchangeIdentity':137,
   'fullyFilledOrderEconomicsVerified':132,
   'canceledPartialOrderFillQuantitiesVerified':5,
   'allOrdersFillBasedNotionalAndFeesReconciled':True,
   'parentCumQuoteEqualFillNotionalOrders':matched_parent,
   'parentCumQuoteDiscrepantFilledOrders':discrepant_filled,
   'parentCumQuoteDiscrepantCanceledPartialOrders':5,
   'parentCumQuoteDiscrepancyTotalOrders':parent_conflicts,
   'executedFillNotionalUSDT':str(fills_quote),
   'executedFillFeesUSDT':str(fills_fees),
   'fillAmountsCrossCheckedAcrossIndependentReports':True,
   'fullAccountHistoryCovered':False,
   'fundingAndNetPnLCertified':False,
   'weexParentFieldSemanticsResolved':False,
   'fullEconomicCertification':False,
   'liveCrashRecoveryCertified':False,
   'releaseGateOverride':False,'exchangeWrites':0}
 target=ROOT/'weex_1000_fill_economics_consolidated.json'
 temp=target.with_suffix('.tmp')
 temp.write_text(json.dumps(report,indent=2),encoding='utf-8');os.replace(temp,target)
 return report
if __name__=='__main__':print(json.dumps(run()))
