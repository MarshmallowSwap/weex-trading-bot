"""Initialize the isolated 1x pilot journal without creating trade intents.

Offline only: never obtains credentials or sends exchange requests. Existing
databases and rows are preserved; no live execution permissions are granted.
"""
import sqlite3
from pathlib import Path
from contextlib import closing
from weex_isolated_pilot_offline_journal import SCHEMA

ROOT=Path(__file__).resolve().parent
DEFAULT_PATH=ROOT/'weex_isolated_pilot.sqlite3'

def initialize(path=DEFAULT_PATH):
    target=Path(path)
    if not target.parent.is_dir():
        raise FileNotFoundError('JOURNAL_DIRECTORY_MISSING')
    with closing(sqlite3.connect(str(target),timeout=10)) as db:
        db.execute('PRAGMA synchronous=FULL')
        db.execute(SCHEMA)
        db.execute('BEGIN IMMEDIATE')
        rows=db.execute('SELECT COUNT(*) FROM pilot_v1').fetchone()[0]
        db.commit()
    return {'state':'PILOT_JOURNAL_READY_NO_SEND',
            'pilotRecords':rows,'ordersSubmitted':0,
            'canSend':False,'canRetry':False,'liveCertified':False}

if __name__=='__main__':
    print(initialize())
