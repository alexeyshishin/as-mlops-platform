import time
from datetime import datetime, timezone

import redis

from config import config

TTL_SECONDS = 24 * 60 * 60
LABEL_MAX_LEN = 60

_client = None


def get_client():
    global _client
    if _client is None:
        _client = redis.Redis(
            host=config.redis_host,
            port=config.redis_port,
            db=config.redis_db,
            password=config.redis_password or None,
            decode_responses=True,
        )
    return _client


def _key(session_id):
    return f"chat:{session_id}"


def _intents_key(session_id):
    return f"chat:{session_id}:intents"


def _meta_key(session_id):
    return f"dialog:meta:{session_id}"


def _seq_key(user_id):
    return f"dialog:seq:{user_id}" if user_id else "dialog:seq"


def _index_key(user_id):
    return f"dialogs:index:{user_id}" if user_id else "dialogs:index"


def append(session_id, text, user_id=None):
    if not session_id:
        return
    client = get_client()
    key = _key(session_id)
    client.rpush(key, text)
    client.expire(key, TTL_SECONDS)
    ensure_dialog_meta(session_id, text, user_id)


def get_history(session_id, window=None):
    if not session_id:
        return []
    client = get_client()
    key = _key(session_id)
    if window is None:
        return client.lrange(key, 0, -1)
    return client.lrange(key, -window, -1)


def ensure_dialog_meta(session_id, first_text, user_id=None):
    if not session_id:
        return
    client = get_client()
    meta_key = _meta_key(session_id)
    if client.exists(meta_key):
        return
    seq = client.incr(_seq_key(user_id))
    created_at = datetime.now(timezone.utc).isoformat()
    label = (first_text or "")[:LABEL_MAX_LEN]
    client.hset(meta_key, mapping={"seq": seq, "label": label, "created_at": created_at})
    client.expire(meta_key, TTL_SECONDS)
    client.zadd(_index_key(user_id), {session_id: time.time()})


def track_intent(session_id, intent):
    if not session_id:
        return
    client = get_client()
    key = _intents_key(session_id)
    client.rpush(key, intent or "")
    client.expire(key, TTL_SECONDS)


def get_dialog_meta(session_id):
    if not session_id:
        return None
    client = get_client()
    meta = client.hgetall(_meta_key(session_id))
    if not meta:
        return None
    intents = client.lrange(_intents_key(session_id), 0, -1)
    return {
        "session_id": session_id,
        "seq": int(meta["seq"]),
        "label": meta["label"],
        "created_at": meta["created_at"],
        "intents_recognized": len({i for i in intents if i}),
    }


def get_dialog_turns(session_id):
    if not session_id:
        return None
    client = get_client()
    if not client.exists(_meta_key(session_id)):
        return None
    texts = client.lrange(_key(session_id), 0, -1)
    intents = client.lrange(_intents_key(session_id), 0, -1)
    return [
        {"text": t, "intent": (intents[i] or None) if i < len(intents) else None}
        for i, t in enumerate(texts)
    ]


def delete_dialog(session_id, user_id=None):
    if not session_id:
        return False
    client = get_client()
    pipe = client.pipeline()
    pipe.delete(_meta_key(session_id))
    pipe.delete(_key(session_id), _intents_key(session_id))
    pipe.zrem(_index_key(user_id), session_id)
    existed = pipe.execute()[0]
    return bool(existed)


def list_recent_dialogs(limit=20, user_id=None):
    client = get_client()
    index_key = _index_key(user_id)
    session_ids = client.zrevrange(index_key, 0, limit - 1)
    dialogs = []
    for session_id in session_ids:
        meta = client.hgetall(_meta_key(session_id))
        if not meta:
            client.zrem(index_key, session_id)
            continue
        dialogs.append(
            {
                "session_id": session_id,
                "seq": int(meta["seq"]),
                "label": meta["label"],
                "created_at": meta["created_at"],
            }
        )
    return dialogs
