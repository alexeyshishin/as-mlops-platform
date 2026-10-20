from fastapi.testclient import TestClient

import history as history_module
import main as main_module
import model as model_module
from main import app


def test_classify_returns_flat_dict_from_pyfunc_batch_response(monkeypatch):
    model_module.model.loaded = True
    monkeypatch.setattr(
        model_module.model,
        "predict",
        lambda text, history: [{"intent": "greeting", "confidence": 0.5}],
    )
    monkeypatch.setattr(history_module, "append", lambda session_id, text, user_id=None: None)
    monkeypatch.setattr(history_module, "track_intent", lambda session_id, intent: None)

    client = TestClient(app)
    try:
        response = client.post("/classify", json={"text": "hi"})
    finally:
        model_module.model.loaded = False

    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "greeting"
    assert body["confidence"] == 0.5
    assert body["route"] == "Короткий разговорный ответ"


def test_classify_known_intent_route_matches_intent_actions(monkeypatch):
    model_module.model.loaded = True
    monkeypatch.setattr(
        model_module.model,
        "predict",
        lambda text, history: [{"intent": "support", "confidence": 0.9}],
    )
    monkeypatch.setattr(history_module, "append", lambda session_id, text, user_id=None: None)
    monkeypatch.setattr(history_module, "track_intent", lambda session_id, intent: None)

    client = TestClient(app)
    try:
        response = client.post("/classify", json={"text": "hi"})
    finally:
        model_module.model.loaded = False

    assert response.status_code == 200
    body = response.json()
    assert body["route"] == main_module.ACTION_BY_INTENT["support"]


def test_classify_unknown_intent_has_no_route_and_no_500(monkeypatch):
    model_module.model.loaded = True
    monkeypatch.setattr(
        model_module.model,
        "predict",
        lambda text, history: [{"intent": "some_future_intent", "confidence": 0.4}],
    )
    monkeypatch.setattr(history_module, "append", lambda session_id, text, user_id=None: None)
    monkeypatch.setattr(history_module, "track_intent", lambda session_id, intent: None)

    client = TestClient(app)
    try:
        response = client.post("/classify", json={"text": "hi"})
    finally:
        model_module.model.loaded = False

    assert response.status_code == 200
    body = response.json()
    assert "route" not in body
    assert body["intent"] == "some_future_intent"


def test_cors_preflight_allows_configured_origin():
    client = TestClient(app)
    response = client.options(
        "/classify",
        headers={
            "Origin": "https://app.alexshishin.ru",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://app.alexshishin.ru"


def test_cors_post_response_includes_allow_origin_header(monkeypatch):
    model_module.model.loaded = True
    monkeypatch.setattr(
        model_module.model,
        "predict",
        lambda text, history: [{"intent": "x", "confidence": 0.5}],
    )
    monkeypatch.setattr(history_module, "append", lambda session_id, text, user_id=None: None)
    monkeypatch.setattr(history_module, "track_intent", lambda session_id, intent: None)

    client = TestClient(app)
    try:
        response = client.post(
            "/classify",
            json={"text": "hi"},
            headers={"Origin": "https://app.alexshishin.ru"},
        )
    finally:
        model_module.model.loaded = False

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://app.alexshishin.ru"


def test_classify_rejects_plain_string_history_with_422_not_500():
    client = TestClient(app)
    response = client.post(
        "/classify",
        json={"history": ["привет"], "text": "hi"},
        headers={"Origin": "https://app.alexshishin.ru"},
    )

    assert response.status_code == 422
    assert response.headers["access-control-allow-origin"] == "https://app.alexshishin.ru"


def test_classify_accepts_role_content_history_turns(monkeypatch):
    model_module.model.loaded = True
    monkeypatch.setattr(
        model_module.model,
        "predict",
        lambda text, history: [{"intent": "x", "confidence": 0.5, "history_seen": history}],
    )
    monkeypatch.setattr(history_module, "append", lambda session_id, text, user_id=None: None)
    monkeypatch.setattr(history_module, "track_intent", lambda session_id, intent: None)

    client = TestClient(app)
    try:
        response = client.post(
            "/classify",
            json={"history": [{"role": "user", "content": "привет"}], "text": "hi"},
        )
    finally:
        model_module.model.loaded = False

    assert response.status_code == 200


def test_cors_preflight_allows_delete():
    client = TestClient(app)
    response = client.options(
        "/dialogs/x",
        headers={
            "Origin": "https://app.alexshishin.ru",
            "Access-Control-Request-Method": "DELETE",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://app.alexshishin.ru"
    assert "DELETE" in response.headers["access-control-allow-methods"]


def test_cors_rejects_unlisted_origin(monkeypatch):
    model_module.model.loaded = True
    monkeypatch.setattr(
        model_module.model,
        "predict",
        lambda text, history: [{"intent": "x", "confidence": 0.5}],
    )
    monkeypatch.setattr(history_module, "append", lambda session_id, text, user_id=None: None)
    monkeypatch.setattr(history_module, "track_intent", lambda session_id, intent: None)

    client = TestClient(app)
    try:
        response = client.post(
            "/classify",
            json={"text": "hi"},
            headers={"Origin": "https://evil.example.com"},
        )
    finally:
        model_module.model.loaded = False

    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers
