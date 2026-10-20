from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

import model as model_module
from config import config


def test_load_uses_alias_uri_not_source():
    fake_version = MagicMock()
    fake_version.source = "models:/m-3f9a8b2c1d4e"
    fake_version.version = "7"
    fake_version.run_id = "run123"
    fake_version.tags = {"dataset_version": "ds-2026-09-11"}

    fake_client = MagicMock()
    fake_client.get_model_version_by_alias.return_value = fake_version

    fake_pyfunc = MagicMock()
    fake_load_model = MagicMock(return_value=fake_pyfunc)

    with patch("model.MlflowClient", return_value=fake_client), patch(
        "mlflow.pyfunc.load_model", fake_load_model
    ), patch("mlflow.set_tracking_uri"):
        m = model_module.Model()
        m.load()

    fake_load_model.assert_called_once_with(
        f"models:/{config.model_name}@{config.model_alias}"
    )
    assert m.loaded is True
    assert m.model_version == "7"
    assert m.dataset_version == "ds-2026-09-11"
    fake_client.get_model_version_by_alias.assert_called_once()


def test_load_falls_back_to_run_tags_when_no_version_tag():
    fake_version = MagicMock()
    fake_version.source = "models:/m-7a1b2c3d4e5f"
    fake_version.version = "3"
    fake_version.run_id = "run456"
    fake_version.tags = {}

    fake_run = MagicMock()
    fake_run.data.tags = {"dataset_version": "ds-from-run"}

    fake_client = MagicMock()
    fake_client.get_model_version_by_alias.return_value = fake_version
    fake_client.get_run.return_value = fake_run

    with patch("model.MlflowClient", return_value=fake_client), patch(
        "mlflow.pyfunc.load_model", return_value=MagicMock()
    ), patch("mlflow.set_tracking_uri"):
        m = model_module.Model()
        m.load()

    assert m.dataset_version == "ds-from-run"


def test_predict_calls_loaded_pyfunc_opaquely():
    m = model_module.Model()
    fake_pyfunc = MagicMock()
    fake_pyfunc.predict.return_value = [{"whatever": "shape", "the": "artifact returns"}]
    m._pyfunc = fake_pyfunc
    m.loaded = True

    result = m.predict("hello", [{"role": "user", "text": "hi"}])

    assert fake_pyfunc.predict.call_count == 1
    called_with = fake_pyfunc.predict.call_args[0][0]
    expected = pd.DataFrame([{"text": "hello", "history": [{"role": "user", "text": "hi"}]}])
    pd.testing.assert_frame_equal(called_with, expected)
    assert result == [{"whatever": "shape", "the": "artifact returns"}]


def test_predict_raises_if_not_loaded():
    m = model_module.Model()
    with pytest.raises(RuntimeError):
        m.predict("hi", None)


def test_predict_survives_real_pyfunc_iterrows_contract():
    class FakePyfuncModel:
        def predict(self, model_input):
            return [
                {"intent": row["text"], "history_len": len(row["history"])}
                for _, row in model_input.iterrows()
            ]

    m = model_module.Model()
    m._pyfunc = FakePyfuncModel()
    m.loaded = True

    result = m.predict("hello", [{"role": "user", "text": "hi"}])

    assert result == [{"intent": "hello", "history_len": 1}]
