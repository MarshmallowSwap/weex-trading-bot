"""User-confirmed exception for one exact manually opened live position.

The exception is scoped to the exchange position identity. A fresh runner
observation must match it; manual positions are excluded from bot capacity.
"""
import hashlib, json, os, time, urllib.request
from pathlib import Path
from weex_execution_cycle import exclusive

PENDING = 'weex_manual_tp_ack_pending.json'
REQUESTS = 'weex_manual_tp_ack_requests.json'
ACKS = 'weex_manual_tp_acknowledged.json'
TTL = 24 * 60 * 60

def identity(position):
    keys = ('id', 'symbol', 'side', 'size', 'openValue', 'cumOpenSize',
            'cumOpenValue', 'createdTime', 'createdMatchSequenceId')
    data = {k: position.get(k) for k in keys}
    if not data.get('symbol') or not data.get('id'):
        raise ValueError('MANUAL_ACK_POSITION_IDENTITY_INCOMPLETE')
    return data

def key(position):
    raw = json.dumps(identity(position), sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(raw.encode()).hexdigest()

def _load(root, name):
    try:
        data = json.loads((Path(root) / name).read_text(encoding='utf-8'))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}

def _save(root, name, data):
    path = Path(root) / name
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(data, indent=2), encoding='utf-8')
    os.replace(tmp, path)

def notify(root, positions, *, now=None):
    now = time.time() if now is None else now
    pending = _load(root, PENDING)
    from monitor import TG
    cfg = json.loads(Path(TG).read_text(encoding='utf-8'))
    for pos in positions:
        try:
            ident = identity(pos); fingerprint = key(pos)
        except ValueError:
            continue
        old = pending.get(fingerprint, {})
        if old.get('expires', 0) > now and now - old.get('sentAt', 0) < 1800:
            continue
        token = hashlib.sha256((fingerprint + ':' + str(int(now))).encode()).hexdigest()[:20]
        pending[fingerprint] = {'token': token, 'identity': ident,
                                'sentAt': now, 'expires': now + TTL}
        _save(root, PENDING, pending)
        side = str(pos.get('side', ''))
        size = str(pos.get('size', ''))
        payload = {
            'chat_id': cfg['telegram_chat_id'],
            'text': (f"⛔ WEEX: nuovi ingressi LIVE sospesi.\n"
                     f"{ident['symbol']} {side} · quantità {size}: non risulta un TP sull'intera posizione.\n\n"
                     "Se l'hai aperta manualmente, puoi autorizzare il runner a ignorare SOLO questo blocco "
                     "per questa precisa posizione. La posizione resta senza TP e non sarà protetta dal runner; "
                     "potranno essere aperti altri ingressi se tutti gli altri controlli passano."),
            'reply_markup': {'inline_keyboard': [[{
                'text': 'Confermo: posizione manuale, ignora questo blocco',
                'callback_data': 'liveack:manual:' + token
            }]]}
        }
        req = urllib.request.Request('https://api.telegram.org/bot' + cfg['telegram_bot_token'] + '/sendMessage',
              json.dumps(payload, ensure_ascii=False).encode(), {'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=15) as response:
            result = json.load(response)
        if not result.get('ok'):
            raise RuntimeError('TELEGRAM_BLOCK_ALERT_REJECTED')
    _save(root, PENDING, pending)

def request_ack(root, token, user, chat, *, now=None):
    now = time.time() if now is None else now
    with exclusive(Path(root) / 'weex_manual_tp_ack.lock'):
        pending = _load(root, PENDING)
        match = next((v for v in pending.values() if v.get('token') == token and v.get('expires', 0) >= now), None)
        if not match:
            return False
        requests = _load(root, REQUESTS)
        requests[token] = {'identity': match['identity'], 'fingerprint': key(match['identity']),
                           'requestedAt': now, 'expires': now + TTL,
                           'user': str(user), 'chat': str(chat)}
        _save(root, REQUESTS, requests)
        return True

def apply_fresh_observation(root, positions, *, now=None):
    """Consume only acknowledgements matching a currently observed position."""
    now = time.time() if now is None else now
    with exclusive(Path(root) / 'weex_manual_tp_ack.lock'):
        current = {key(p): p for p in positions}
        requests = _load(root, REQUESTS); acks = _load(root, ACKS)
        changed = False
        for token, req in list(requests.items()):
            fp = req.get('fingerprint')
            if req.get('expires', 0) < now:
                requests.pop(token, None); changed = True
            elif fp in current:
                acks[fp] = {'identity': identity(current[fp]), 'acknowledgedAt': req['requestedAt'],
                            'user': req.get('user'), 'chat': req.get('chat')}
                requests.pop(token, None); changed = True
        # A closed or materially changed position loses its exception automatically.
        for fp in list(acks):
            if fp not in current:
                acks.pop(fp, None); changed = True
        if changed:
            _save(root, REQUESTS, requests); _save(root, ACKS, acks)
        return set(acks)
