"""Persisted user-selected trading mode and durable manual-entry queue.

This module never talks to WEEX or sends orders. A consumer must independently
revalidate safety gates and execute queued requests through the lifecycle.
"""
import json, os, re, sqlite3, time, uuid
from decimal import Decimal, InvalidOperation
from pathlib import Path

MODES = ('automatic', 'alerts_only', 'automatic_manual', 'manual_only')
SYMBOL_RE = re.compile(r'^[A-Z0-9]{2,24}USDT$')
MANUAL_TTL_SECONDS = 90

def connect(root):
    p=Path(root)/'weex_trading_modes.sqlite3'
    c=sqlite3.connect(p, timeout=10)
    c.row_factory=sqlite3.Row
    c.execute('PRAGMA journal_mode=WAL')
    c.executescript("""
      CREATE TABLE IF NOT EXISTS mode_v1(id INTEGER PRIMARY KEY CHECK(id=1), mode TEXT NOT NULL, updated REAL NOT NULL);
      INSERT OR IGNORE INTO mode_v1 VALUES(1,'alerts_only',0);
      CREATE TABLE IF NOT EXISTS manual_requests_v1(
        id TEXT PRIMARY KEY, symbol TEXT NOT NULL, side TEXT, state TEXT NOT NULL,
        requested_at REAL NOT NULL, requested_by TEXT NOT NULL, detail TEXT);
      CREATE INDEX IF NOT EXISTS manual_requests_state ON manual_requests_v1(state, requested_at);
      CREATE TABLE IF NOT EXISTS mode_events_v1(id INTEGER PRIMARY KEY AUTOINCREMENT, at REAL NOT NULL,
        action TEXT NOT NULL, actor TEXT NOT NULL, detail TEXT NOT NULL);
    """)
    columns={r[1] for r in c.execute('PRAGMA table_info(manual_requests_v1)')}
    if 'side' not in columns:c.execute('ALTER TABLE manual_requests_v1 ADD COLUMN side TEXT')
    c.commit()
    return c

def get_mode(root):
    c=connect(root)
    try:
        row=c.execute('SELECT mode,updated FROM mode_v1 WHERE id=1').fetchone()
        return {'mode':row['mode'],'updated':row['updated']}
    finally:c.close()

def set_mode(root, mode, actor):
    if mode not in MODES: raise ValueError('INVALID_TRADING_MODE')
    if not str(actor).strip(): raise ValueError('ACTOR_REQUIRED')
    c=connect(root)
    try:
        c.execute('BEGIN IMMEDIATE')
        c.execute('UPDATE mode_v1 SET mode=?,updated=? WHERE id=1',(mode,time.time()))
        if mode not in ('automatic_manual','manual_only'):
            c.execute("UPDATE manual_requests_v1 SET state='REJECTED',detail=? WHERE state='PENDING'",
                      (json.dumps({'reason':'TRADING_MODE_CHANGED'}),))
        c.execute('INSERT INTO mode_events_v1(at,action,actor,detail) VALUES(?,?,?,?)',
                  (time.time(),'SET_MODE',str(actor),json.dumps({'mode':mode})))
        c.commit()
        return get_mode(root)
    except BaseException:
        c.rollback(); raise
    finally:c.close()

def normalize_symbol(raw):
    s=str(raw or '').strip().upper()
    if s.endswith('USDT'): symbol=s
    else: symbol=s+'USDT'
    if not SYMBOL_RE.fullmatch(symbol): raise ValueError('SYMBOL_FORMAT_INVALID')
    return symbol

def normalize_side(raw):
    side=str(raw or '').strip().upper()
    if side not in ('LONG','SHORT'):raise ValueError('MANUAL_DIRECTION_REQUIRED')
    return side

def validate_entry_book(book, *, manual_override=False):
    """Require usable execution quotes; only automatic entries require candidate liquidity gates."""
    if not isinstance(book,dict) or book.get('status')!='OK':raise ValueError('LIVE_ORDERBOOK_UNAVAILABLE')
    try:
        bid=Decimal(str(book['bestBid']));ask=Decimal(str(book['bestAsk']))
        if not bid.is_finite() or not ask.is_finite() or bid<=0 or ask<bid:
            raise ValueError('LIVE_ORDERBOOK_QUOTES_INVALID')
    except (KeyError,InvalidOperation,TypeError):raise ValueError('LIVE_ORDERBOOK_QUOTES_INVALID') from None
    if not manual_override and (book.get('passed') is not True or book.get('depthUnitVerified') is not True):
        raise ValueError('LIVE_BOOK_UNVERIFIED')
    return {'bestBid':bid,'bestAsk':ask}

def parse_manual_command(text):
    """Return (normalized symbol, side) only for an exact two-token command."""
    parts=str(text or '').strip().split()
    if len(parts)!=2:return None
    try:symbol=normalize_symbol(parts[0])
    except ValueError:return None
    return symbol,normalize_side(parts[1])

def enqueue_manual(root, raw_symbol, raw_side, actor, *, now=None):
    symbol=normalize_symbol(raw_symbol)
    side=normalize_side(raw_side)
    if not str(actor).strip(): raise ValueError('ACTOR_REQUIRED')
    c=connect(root)
    try:
        c.execute('BEGIN IMMEDIATE')
        mode=c.execute('SELECT mode FROM mode_v1 WHERE id=1').fetchone()['mode']
        if mode not in ('automatic_manual','manual_only'):
            c.rollback(); raise PermissionError('MANUAL_ENTRY_MODE_DISABLED')
        # Avoid overlapping requests for the same symbol, including opposite sides.
        existing=c.execute("SELECT id FROM manual_requests_v1 WHERE symbol=? AND state IN ('PENDING','PROCESSING')",(symbol,)).fetchone()
        if existing:
            c.rollback(); raise ValueError('MANUAL_SYMBOL_ALREADY_QUEUED')
        ident='manual_'+uuid.uuid4().hex
        stamp=time.time() if now is None else float(now)
        c.execute('INSERT INTO manual_requests_v1(id,symbol,side,state,requested_at,requested_by,detail) VALUES(?,?,?,?,?,?,?)',
                  (ident,symbol,side,'PENDING',stamp,str(actor),None))
        c.execute('INSERT INTO mode_events_v1(at,action,actor,detail) VALUES(?,?,?,?)',
                  (stamp,'MANUAL_REQUEST',str(actor),json.dumps({'id':ident,'symbol':symbol,'side':side})))
        c.commit()
        return {'id':ident,'symbol':symbol,'side':side,'state':'PENDING','requestedAt':stamp,
                'expiresAt':stamp+MANUAL_TTL_SECONDS}
    except BaseException:
        if c.in_transaction: c.rollback()
        raise
    finally:c.close()

def claim_next(root, request_id=None, *, now=None):
    """Atomically claim one request; caller must still run all live gates."""
    stamp=time.time() if now is None else float(now)
    c=connect(root)
    try:
        c.execute('BEGIN IMMEDIATE')
        c.execute("UPDATE manual_requests_v1 SET state='REJECTED',detail=? WHERE state='PENDING' AND requested_at<?",
                  (json.dumps({'reason':'MANUAL_REQUEST_EXPIRED'}),stamp-MANUAL_TTL_SECONDS))
        if request_id is None:
            row=c.execute("SELECT * FROM manual_requests_v1 WHERE state='PENDING' ORDER BY requested_at,id LIMIT 1").fetchone()
        else:
            row=c.execute("SELECT * FROM manual_requests_v1 WHERE id=? AND state='PENDING'",(request_id,)).fetchone()
        if not row: c.commit(); return None
        if row['side'] not in ('LONG','SHORT'):
            c.execute("UPDATE manual_requests_v1 SET state='REVIEW_REQUIRED',detail=? WHERE id=?",
                      (json.dumps({'reason':'MANUAL_DIRECTION_MISSING'}),row['id']))
            c.commit();return None
        c.execute("UPDATE manual_requests_v1 SET state='PROCESSING' WHERE id=? AND state='PENDING'",(row['id'],))
        c.commit()
        return dict(row) | {'state':'PROCESSING'}
    except BaseException:
        c.rollback(); raise
    finally:c.close()

def cancel_pending_manual(root, reason):
    """Cancel unclaimed user intents when the live gate or mode is switched off."""
    c=connect(root)
    try:
        c.execute('BEGIN IMMEDIATE')
        count=c.execute("UPDATE manual_requests_v1 SET state='REJECTED',detail=? WHERE state='PENDING'",
                        (json.dumps({'reason':str(reason)}),)).rowcount
        if count:
            c.execute('INSERT INTO mode_events_v1(at,action,actor,detail) VALUES(?,?,?,?)',
                      (time.time(),'CANCEL_PENDING_MANUAL','system',json.dumps({'reason':str(reason),'count':count})))
        c.commit();return count
    except BaseException:
        c.rollback();raise
    finally:c.close()

def cancel_pending_request(root, request_id, reason):
    c=connect(root)
    try:
        c.execute('BEGIN IMMEDIATE')
        cur=c.execute("UPDATE manual_requests_v1 SET state='REJECTED',detail=? WHERE id=? AND state='PENDING'",
                      (json.dumps({'reason':str(reason)}),str(request_id)))
        c.commit();return cur.rowcount==1
    except BaseException:
        c.rollback();raise
    finally:c.close()

def finish_request(root, request_id, state, detail=None):
    if state not in ('PROTECTED','CLOSED','REJECTED','REVIEW_REQUIRED'): raise ValueError('INVALID_MANUAL_FINAL_STATE')
    c=connect(root)
    try:
        c.execute('BEGIN IMMEDIATE')
        cur=c.execute("UPDATE manual_requests_v1 SET state=?,detail=? WHERE id=? AND state='PROCESSING'",
                      (state,json.dumps(detail or {},sort_keys=True),request_id))
        if cur.rowcount!=1: c.rollback(); return False
        c.commit(); return True
    except BaseException:
        c.rollback(); raise
    finally:c.close()
