from fastapi.testclient import TestClient

import model as model_module
from main import app


def test_health_always_ok():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_503_before_model_loaded():
    model_module.model.loaded = False
    client = TestClient(app)
    response = client.get("/ready")
    assert response.status_code == 503


def test_ready_200_after_model_loaded():
    model_module.model.loaded = True
    try:
        client = TestClient(app)
        response = client.get("/ready")
        assert response.status_code == 200
    finally:
        model_module.model.loaded = False
