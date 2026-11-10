"""Scoped empirical book-unit evidence. No inference is extended to untested symbols."""
import json
from datetime import datetime,timezone
from decimal import Decimal
from pathlib import Path
FIELDS=('symbol','baseAsset','quoteAsset','contractType','quantityPrecision','contractVal')
def fingerprint(meta):return {k:str(meta[k]) for k in FIELDS}
def verify(symbol,meta,book,evidence=None,at=None):
    try:
        if evidence is None:evidence=json.loads(Path(__file__).with_name('weex_depth_unit_evidence.json').read_text(encoding='utf-8'))
        at=at or datetime.now(timezone.utc)
        row=evidence['symbols'][symbol]
        age=(at-datetime.fromisoformat(row.get('checkedAt',evidence['checkedAt']))).total_seconds()
        if evidence.get('version')!=1 or not 0<=age<=7*86400:return False,'EVIDENCE_MISSING_OR_EXPIRED'
        if row['metadata']!=fingerprint(meta) or meta['symbol']!=symbol:return False,'UNIT_METADATA_CHANGED'
        if meta['quoteAsset']!='USDT' or meta['contractType']!='PERPETUAL':return False,'UNSUPPORTED_CONTRACT'
        stats=row['restEvidence'];factor=Decimal(str(meta['contractVal']))
        if (stats['rounds']<3 or len(set(stats['depthUpdateIds']))<3 or stats['levels']<400
                or stats['uniqueTrades']<100 or stats['tradeQuoteErrors']!=0 or stats['rawQuantityStepViolations']!=0):return False,'INSUFFICIENT_EMPIRICAL_EVIDENCE'
        if row['method']=='LOT_GRID_ELIMINATES_CONTRACT_COUNTS':
            if not 0<factor<1 or stats['contractInterpretationStepViolations']<100:return False,'INCONCLUSIVE_LOT_EVIDENCE'
        elif row['method']=='PUBLIC_UI_BASE_UNIT_MATCH':
            ui=row['uiEvidence']
            # With one base unit per contract the two conversions are identical.
            # Still require the independently observed UI/API quantity matches.
            expected_contract_matches=ui['bestBaseMatches'] if factor==1 else 0
            if (ui['symbol']!=symbol or ui['visibleAmountUnit']!=meta['baseAsset'] or ui['bestBaseMatches']<15
                    or ui['bestContractConvertedMatches']!=expected_contract_matches or factor<=0):return False,'INCONCLUSIVE_UI_EVIDENCE'
        else:return False,'UNKNOWN_EVIDENCE_METHOD'
        step=Decimal(10)**-int(meta['quantityPrecision'])
        for side in ('bids','asks'):
            if not book[side]:return False,'EMPTY_BOOK'
            for p,q in book[side]:
                q=Decimal(str(q))
                if not q.is_finite() or q<0 or q%step:return False,'BOOK_QUANTITY_GRID_CHANGED'
        return True,'EMPIRICALLY_VALIDATED_BASE_ASSET'
    except (KeyError,ValueError,TypeError,OSError,ArithmeticError):return False,'UNIT_EVIDENCE_UNAVAILABLE'
