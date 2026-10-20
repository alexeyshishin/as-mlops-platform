import itertools

import fakeredis
import pytest

import history as history_module


@pytest.fixture(autouse=True)
def fake_redis_client(monkeypatch):
    fake = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(history_module, "_client", fake)
    monkeypatch.setattr(history_module, "get_client", lambda: fake)
    yield fake


def test_append_and_get_history(fake_redis_client):
    history_module.append("session-1", "hello")
    history_module.append("session-1", "world")

    assert history_module.get_history("session-1") == ["hello", "world"]
    assert fake_redis_client.ttl("chat:session-1") > 0


def test_append_noop_without_session_id(fake_redis_client):
    history_module.append(None, "hello")
    assert fake_redis_client.keys("chat:*") == []


def test_get_history_window(fake_redis_client):
    for i in range(5):
        history_module.append("session-2", f"msg-{i}")
    assert history_module.get_history("session-2", window=2) == ["msg-3", "msg-4"]


def test_get_history_without_session_id_returns_empty(fake_redis_client):
    assert history_module.get_history(None) == []


def test_ensure_dialog_meta_creates_once(fake_redis_client):
    history_module.ensure_dialog_meta("session-3", "hello there, first message")

    meta = fake_redis_client.hgetall("dialog:meta:session-3")
    assert meta["seq"] == "1"
    assert meta["label"] == "hello there, first message"
    assert fake_redis_client.ttl("dialog:meta:session-3") > 0
    assert fake_redis_client.zscore("dialogs:index", "session-3") is not None

    history_module.ensure_dialog_meta("session-3", "second message should be ignored")
    meta_again = fake_redis_client.hgetall("dialog:meta:session-3")
    assert meta_again["label"] == "hello there, first message"


def test_ensure_dialog_meta_truncates_label(fake_redis_client):
    long_text = "x" * 200
    history_module.ensure_dialog_meta("session-4", long_text)
    meta = fake_redis_client.hgetall("dialog:meta:session-4")
    assert len(meta["label"]) == 60


def test_ensure_dialog_meta_noop_without_session_id(fake_redis_client):
    history_module.ensure_dialog_meta(None, "hello")
    assert fake_redis_client.keys("dialog:meta:*") == []


def test_append_creates_dialog_meta(fake_redis_client):
    history_module.append("session-5", "first user text")
    meta = fake_redis_client.hgetall("dialog:meta:session-5")
    assert meta["label"] == "first user text"


def test_track_intent_and_get_dialog_meta(fake_redis_client):
    history_module.ensure_dialog_meta("session-6", "hi")
    history_module.track_intent("session-6", "billing")
    history_module.track_intent("session-6", "billing")
    history_module.track_intent("session-6", "support")

    meta = history_module.get_dialog_meta("session-6")

    assert meta["session_id"] == "session-6"
    assert meta["seq"] == 1
    assert meta["label"] == "hi"
    assert meta["intents_recognized"] == 2


def test_track_intent_noop_without_session_id_or_intent(fake_redis_client):
    history_module.track_intent(None, "billing")
    assert fake_redis_client.keys("chat:*:intents") == []

    history_module.track_intent("session-7", None)
    assert fake_redis_client.lrange("chat:session-7:intents", 0, -1) == [""]


def test_get_dialog_meta_returns_none_when_missing(fake_redis_client):
    assert history_module.get_dialog_meta("no-such-session") is None


def test_get_dialog_meta_returns_none_without_session_id(fake_redis_client):
    assert history_module.get_dialog_meta(None) is None


def test_list_recent_dialogs_newest_first(fake_redis_client, monkeypatch):
    counter = itertools.count(100.0, 100.0)
    monkeypatch.setattr(history_module.time, "time", lambda: next(counter))

    history_module.ensure_dialog_meta("session-a", "first dialog")
    history_module.ensure_dialog_meta("session-b", "second dialog")

    dialogs = history_module.list_recent_dialogs(limit=20)

    assert [d["session_id"] for d in dialogs] == ["session-b", "session-a"]
    assert dialogs[0]["label"] == "second dialog"
    assert "intents_recognized" not in dialogs[0]


def test_list_recent_dialogs_respects_limit(fake_redis_client):
    for i in range(3):
        history_module.ensure_dialog_meta(f"session-{i}", f"text-{i}")

    dialogs = history_module.list_recent_dialogs(limit=2)
    assert len(dialogs) == 2


def test_list_recent_dialogs_empty_when_no_dialogs(fake_redis_client):
    assert history_module.list_recent_dialogs() == []


def test_per_user_seq_independence(fake_redis_client):
    history_module.append("u1-a", "hi", user_id="u1")
    history_module.append("u1-b", "hi", user_id="u1")
    history_module.append("u2-a", "hi", user_id="u2")

    assert fake_redis_client.hget("dialog:meta:u1-a", "seq") == "1"
    assert fake_redis_client.hget("dialog:meta:u1-b", "seq") == "2"
    assert fake_redis_client.hget("dialog:meta:u2-a", "seq") == "1"
    assert fake_redis_client.get("dialog:seq:u1") == "2"
    assert fake_redis_client.get("dialog:seq:u2") == "1"
    assert fake_redis_client.get("dialog:seq") is None


def test_per_user_index_scoping(fake_redis_client):
    history_module.append("u1-a", "hi", user_id="u1")

    assert fake_redis_client.zscore("dialogs:index:u1", "u1-a") is not None
    assert fake_redis_client.zscore("dialogs:index", "u1-a") is None


def test_list_recent_dialogs_user_filter(fake_redis_client):
    history_module.append("u1-a", "u1 first", user_id="u1")
    history_module.append("u1-b", "u1 second", user_id="u1")
    history_module.append("u2-a", "u2 first", user_id="u2")

    u1_dialogs = history_module.list_recent_dialogs(user_id="u1")
    u2_dialogs = history_module.list_recent_dialogs(user_id="u2")

    assert sorted(d["session_id"] for d in u1_dialogs) == ["u1-a", "u1-b"]
    assert [d["session_id"] for d in u2_dialogs] == ["u2-a"]


def test_global_fallback_regression(fake_redis_client):
    history_module.append("g-a", "global one")
    history_module.append("g-b", "global two")

    assert fake_redis_client.get("dialog:seq") == "2"
    dialogs = history_module.list_recent_dialogs()
    assert sorted(d["session_id"] for d in dialogs) == ["g-a", "g-b"]
    assert history_module.list_recent_dialogs(user_id="u1") == []


def test_intents_recognized_ignores_empty_sentinels(fake_redis_client):
    history_module.ensure_dialog_meta("session-int", "hi")
    history_module.track_intent("session-int", "billing")
    history_module.track_intent("session-int", None)
    history_module.track_intent("session-int", "billing")
    history_module.track_intent("session-int", "")
    history_module.track_intent("session-int", "support")

    meta = history_module.get_dialog_meta("session-int")
    assert meta["intents_recognized"] == 2


def test_get_dialog_turns_aligned_pairing(fake_redis_client):
    history_module.append("turns-1", "first")
    history_module.track_intent("turns-1", "billing")
    history_module.append("turns-1", "second")
    history_module.track_intent("turns-1", None)

    turns = history_module.get_dialog_turns("turns-1")
    assert turns == [
        {"text": "first", "intent": "billing"},
        {"text": "second", "intent": None},
    ]


def test_get_dialog_turns_missing_intent_tail_is_null(fake_redis_client):
    history_module.append("turns-2", "first")
    history_module.track_intent("turns-2", "billing")
    history_module.append("turns-2", "second")

    turns = history_module.get_dialog_turns("turns-2")
    assert turns == [
        {"text": "first", "intent": "billing"},
        {"text": "second", "intent": None},
    ]


def test_get_dialog_turns_returns_none_when_missing(fake_redis_client):
    assert history_module.get_dialog_turns("no-such-session") is None
    assert history_module.get_dialog_turns(None) is None


def test_list_recent_dialogs_lazy_gc_removes_metaless_index_entry(fake_redis_client):
    history_module.append("gc-a", "still here")
    fake_redis_client.zadd("dialogs:index", {"gc-ghost": 1.0})

    dialogs = history_module.list_recent_dialogs()

    assert [d["session_id"] for d in dialogs] == ["gc-a"]
    assert fake_redis_client.zscore("dialogs:index", "gc-ghost") is None


def test_delete_dialog_clears_keys_and_index(fake_redis_client):
    history_module.append("del-a", "to be deleted", user_id="u1")
    history_module.track_intent("del-a", "billing")

    assert fake_redis_client.exists("dialog:meta:del-a") == 1
    assert fake_redis_client.exists("chat:del-a") == 1
    assert fake_redis_client.exists("chat:del-a:intents") == 1
    assert fake_redis_client.zscore("dialogs:index:u1", "del-a") is not None

    result = history_module.delete_dialog("del-a", user_id="u1")

    assert result is True
    assert fake_redis_client.exists("dialog:meta:del-a") == 0
    assert fake_redis_client.exists("chat:del-a") == 0
    assert fake_redis_client.exists("chat:del-a:intents") == 0
    assert fake_redis_client.zscore("dialogs:index:u1", "del-a") is None


def test_delete_dialog_missing_returns_false(fake_redis_client):
    assert history_module.delete_dialog("no-such-session", user_id="u1") is False


def test_delete_dialog_none_returns_false(fake_redis_client):
    assert history_module.delete_dialog(None) is False


def test_delete_dialog_zrem_only_given_user_index(fake_redis_client):
    history_module.append("u1-a", "u1 first", user_id="u1")
    history_module.append("u2-a", "u2 first", user_id="u2")

    result = history_module.delete_dialog("u1-a", user_id="u1")

    assert result is True
    assert fake_redis_client.zscore("dialogs:index:u1", "u1-a") is None
    assert fake_redis_client.zscore("dialogs:index:u2", "u2-a") is not None


def test_delete_dialog_global_fallback_clears_index(fake_redis_client):
    history_module.append("g-a", "global one")

    assert fake_redis_client.zscore("dialogs:index", "g-a") is not None

    result = history_module.delete_dialog("g-a")

    assert result is True
    assert fake_redis_client.zscore("dialogs:index", "g-a") is None
