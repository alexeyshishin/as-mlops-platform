import fakeredis
import pytest
from fastapi.testclient import TestClient

import history as history_module
from main import app


@pytest.fixture(autouse=True)
def fake_redis_client(monkeypatch):
    fake = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(history_module, "_client", fake)
    monkeypatch.setattr(history_module, "get_client", lambda: fake)
    yield fake


@pytest.fixture()
def client():
    return TestClient(app)


def test_get_dialog_turns_returns_paired_turns(client):
    history_module.append("session-turns", "first message")
    history_module.track_intent("session-turns", "billing")
    history_module.append("session-turns", "second message")
    history_module.track_intent("session-turns", None)

    response = client.get("/dialogs/session-turns/turns")

    assert response.status_code == 200
    body = response.json()
    assert body["session_id"] == "session-turns"
    assert body["turns"] == [
        {"text": "first message", "intent": "billing"},
        {"text": "second message", "intent": None},
    ]


def test_get_dialog_turns_unknown_session_returns_404(client):
    response = client.get("/dialogs/no-such-session/turns")

    assert response.status_code == 404


def test_list_dialogs_filters_by_user_id(client):
    history_module.append("u1-a", "u1 first", user_id="u1")
    history_module.append("u1-b", "u1 second", user_id="u1")
    history_module.append("u2-a", "u2 first", user_id="u2")

    response = client.get("/dialogs", params={"user_id": "u1"})

    assert response.status_code == 200
    session_ids = sorted(d["session_id"] for d in response.json()["dialogs"])
    assert session_ids == ["u1-a", "u1-b"]


def test_delete_dialog_returns_204_and_clears_keys(client, fake_redis_client):
    history_module.append("d1", "hello", user_id="u1")
    history_module.track_intent("d1", "billing")

    response = client.delete("/dialogs/d1", params={"user_id": "u1"})

    assert response.status_code == 204
    assert fake_redis_client.exists("dialog:meta:d1") == 0
    assert fake_redis_client.exists("chat:d1") == 0
    assert fake_redis_client.exists("chat:d1:intents") == 0
    assert fake_redis_client.zscore("dialogs:index:u1", "d1") is None


def test_delete_dialog_missing_returns_404(client):
    response = client.delete("/dialogs/no-such-session", params={"user_id": "u1"})

    assert response.status_code == 404


def test_delete_dialog_per_user_isolation(client, fake_redis_client):
    history_module.append("u1-a", "u1 first", user_id="u1")
    history_module.append("u2-a", "u2 first", user_id="u2")

    response = client.delete("/dialogs/u1-a", params={"user_id": "u1"})

    assert response.status_code == 204
    assert fake_redis_client.zscore("dialogs:index:u1", "u1-a") is None
    assert fake_redis_client.zscore("dialogs:index:u2", "u2-a") is not None


def test_delete_dialog_global_fallback_returns_204(client, fake_redis_client):
    history_module.append("g-a", "global one")

    response = client.delete("/dialogs/g-a")

    assert response.status_code == 204
    assert fake_redis_client.zscore("dialogs:index", "g-a") is None
