import os


class Config:
    def __init__(self):
        self.mlflow_tracking_uri = os.environ.get(
            "MLFLOW_TRACKING_URI", "http://mlflow.mlops.svc.cluster.local:5000"
        )
        self.mlflow_tracking_username = os.environ.get("MLFLOW_TRACKING_USERNAME", "")
        self.mlflow_tracking_password = os.environ.get("MLFLOW_TRACKING_PASSWORD", "")

        self.model_name = os.environ.get("MODEL_NAME", "intent-classifier")
        self.model_alias = os.environ.get("MODEL_ALIAS", "Serving-Production")

        self.mlflow_s3_endpoint_url = os.environ.get(
            "MLFLOW_S3_ENDPOINT_URL", "http://minio.mlops.svc.cluster.local:9000"
        )
        self.aws_access_key_id = os.environ.get("AWS_ACCESS_KEY_ID", "")
        self.aws_secret_access_key = os.environ.get("AWS_SECRET_ACCESS_KEY", "")

        self.redis_host = os.environ.get("REDIS_HOST", "redis-master.mlops.svc.cluster.local")
        self.redis_port = int(os.environ.get("REDIS_PORT", "6379"))
        self.redis_db = int(os.environ.get("REDIS_DB", "1"))
        self.redis_password = os.environ.get("REDIS_PASSWORD", "")

        self.debug = os.environ.get("DEBUG", "false").lower() == "true"

    def apply_mlflow_env(self):
        os.environ.setdefault("MLFLOW_S3_ENDPOINT_URL", self.mlflow_s3_endpoint_url)
        if self.aws_access_key_id:
            os.environ.setdefault("AWS_ACCESS_KEY_ID", self.aws_access_key_id)
        if self.aws_secret_access_key:
            os.environ.setdefault("AWS_SECRET_ACCESS_KEY", self.aws_secret_access_key)


config = Config()
