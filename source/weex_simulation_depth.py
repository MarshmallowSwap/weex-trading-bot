"""Simulation-only empirical depth units; never validates settlement semantics."""
from datetime import datetime,timezone
from weex_simulation_domain import SIM
from weex_depth_evidence import verify
from orderbook_liquidity import parse_book

def verify_simulation_units(symbol,metadata,book,evidence,*,source_host,at=None):
    try:
        if source_host!=SIM or evidence.get('sourceHost')!=SIM:
            return False,'SIMULATION_EVIDENCE_HOST_MISMATCH'
        at=at or datetime.now(timezone.utc)
        age=(at-datetime.fromisoformat(evidence['checkedAt'])).total_seconds()
        if not 0<=age<=24*3600:return False,'SIMULATION_EVIDENCE_EXPIRED'
        return verify(symbol,metadata,book,evidence,at=at)
    except (AttributeError,KeyError,TypeError,ValueError):return False,'SIMULATION_EVIDENCE_UNAVAILABLE'

def assess(symbol,metadata,book,evidence,*,source_host,at=None):
    valid,reason=verify_simulation_units(symbol,metadata,book,evidence,source_host=source_host,at=at)
    result=parse_book(symbol,book)
    result.update(depthUnitVerified=valid,depthUnitStatus=reason,sourceHost=source_host,
                  depthUnitOfficiallyConfirmed=False,contractSettlementValidated=False)
    if valid:
        result.update(top15BidNotional=result['rawPriceTimesSizeBid'],top15AskNotional=result['rawPriceTimesSizeAsk'],
            depthQuantityUnit=metadata['baseAsset'],notionalFormula='price * size',contractValApplied=False)
    return result
