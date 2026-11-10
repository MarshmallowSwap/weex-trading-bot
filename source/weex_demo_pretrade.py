"""Supervised demo-only market eligibility report; no order APIs or credentials."""
import argparse,json
from datetime import datetime,timezone
from pathlib import Path
from weex_demo_book_readonly import assess

def run(snapshot_path,signal_report_path,asset):
    snapshot=json.loads(Path(snapshot_path).read_text(encoding='utf-8'))
    signals=json.loads(Path(signal_report_path).read_text(encoding='utf-8'))
    market=next(r for r in signals['results'] if r['symbol']==asset+'USDT')
    report=assess(snapshot,asset,market)
    report.update(checkedAt=datetime.now(timezone.utc).isoformat(),
                  signalCheckedAt=market['checkedAt'],momentum=market.get('momentum'),trend=market.get('trend'),
                  automaticBotReady=False,publicApiUnitEvidenceUnchanged=True)
    return report

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot',required=True);parser.add_argument('--signals',required=True)
    parser.add_argument('--asset',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args()
    try:report=run(args.snapshot,args.signals,args.asset)
    except (ValueError,KeyError,TypeError,OSError,StopIteration,ArithmeticError) as exc:
        report={'marketEligibility':'WAIT','orderPermitted':False,'ordersSubmitted':False,
                'errorType':type(exc).__name__,'reason':str(exc) if isinstance(exc,ValueError) else 'INVALID_SNAPSHOT_OR_SIGNAL'}
    Path(args.output).write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report))
