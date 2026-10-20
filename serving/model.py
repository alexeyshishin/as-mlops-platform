import logging
import os

import mlflow
import pandas as pd
from mlflow import MlflowClient

from config import config

logger = logging.getLogger(__name__)


class Model:
    def __init__(self):
        self.loaded = False
        self.model_version = None
        self.dataset_version = None
        self._pyfunc = None

    def load(self):
        config.apply_mlflow_env()
        mlflow.set_tracking_uri(config.mlflow_tracking_uri)
        if config.mlflow_tracking_username:
            os.environ.setdefault("MLFLOW_TRACKING_USERNAME", config.mlflow_tracking_username)
        if config.mlflow_tracking_password:
            os.environ.setdefault("MLFLOW_TRACKING_PASSWORD", config.mlflow_tracking_password)

        client = MlflowClient(tracking_uri=config.mlflow_tracking_uri)
        model_version = client.get_model_version_by_alias(config.model_name, config.model_alias)

        pyfunc = mlflow.pyfunc.load_model(f"models:/{config.model_name}@{config.model_alias}")

        dataset_version = None
        tags = model_version.tags or {}
        if "dataset_version" in tags:
            dataset_version = tags["dataset_version"]
        else:
            try:
                run = client.get_run(model_version.run_id)
                dataset_version = run.data.tags.get("dataset_version")
            except Exception:
                dataset_version = None

        self._pyfunc = pyfunc
        self.model_version = model_version.version
        self.dataset_version = dataset_version
        self.loaded = True
        logger.info(
            "model loaded name=%s alias=%s version=%s dataset_version=%s",
            config.model_name,
            config.model_alias,
            self.model_version,
            self.dataset_version,
        )

    def predict(self, text, history):
        if not self.loaded or self._pyfunc is None:
            raise RuntimeError("model is not loaded")
        model_input = pd.DataFrame([{"text": text, "history": history or []}])
        return self._pyfunc.predict(model_input)


model = Model()
