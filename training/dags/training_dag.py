from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from airflow.providers.cncf.kubernetes.secret import Secret
from kubernetes.client import models as k8s

default_args = {
    'owner': 'mlops',
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG(
    'intent-classification-pipeline',
    default_args=default_args,
    description='Intent classification GigaEvo model training pipeline!',
    schedule=None,
    start_date=datetime(2026, 9, 11),
    catchup=False,
    dagrun_timeout=timedelta(hours=9),
)

def log_start():
    print('MloPS Pipeline started')

start = PythonOperator(
    task_id='start',
    python_callable=log_start,
    dag=dag,
)

gigaevo_train_and_register = KubernetesPodOperator(
    task_id='gigaevo_train_and_register',
    name='gigaevo-train-and-register',
    namespace='mlops',
    image='git.alexshishin.ru/mlops/training:latest',
    in_cluster=True,
    get_logs=True,
    on_finish_action='delete_succeeded_pod',
    execution_timeout=timedelta(hours=6),
    env_vars={
        'MLFLOW_TRACKING_URI': 'http://mlflow.mlops.svc.cluster.local:5000',
        'MLFLOW_S3_ENDPOINT_URL': 'http://minio.mlops.svc.cluster.local:9000',
        'REDIS_HOST': 'redis-master.mlops.svc.cluster.local',
        'REDIS_PORT': '6379',
        'REDIS_DB': '2',
        'LLAMA_N_THREADS': '6',
    },
    container_resources=k8s.V1ResourceRequirements(
        requests={'cpu': '2', 'memory': '6Gi'},
        limits={'cpu': '6', 'memory': '10Gi'},
    ),
    secrets=[
        Secret('env', 'MLFLOW_TRACKING_USERNAME', 'mlflow-basic-auth-secret', 'username'),
        Secret('env', 'MLFLOW_TRACKING_PASSWORD', 'mlflow-basic-auth-secret', 'password'),
        Secret('env', 'AWS_ACCESS_KEY_ID', 'minio-secret', 'root-user'),
        Secret('env', 'AWS_SECRET_ACCESS_KEY', 'minio-secret', 'root-password'),
        Secret('env', 'REDIS_PASSWORD', 'redis-secret', 'redis-password'),
    ],
    dag=dag,
)

distill_intent_classifier = KubernetesPodOperator(
    task_id='distill_intent_classifier',
    name='distill-intent-classifier',
    namespace='mlops',
    image='git.alexshishin.ru/mlops/training:latest',
    # Образ по умолчанию запускает run_gigaevo_pipeline.py (CMD/ENTRYPOINT в
    # Dockerfile) — здесь явно переопределяем команду на скрипт дистиллера
    cmds=['python', 'distilled_intent_classifier.py'],
    in_cluster=True,
    get_logs=True,
    on_finish_action='delete_succeeded_pod',
    execution_timeout=timedelta(hours=2),
    env_vars={
        'MLFLOW_TRACKING_URI': 'http://mlflow.mlops.svc.cluster.local:5000',
        'MLFLOW_S3_ENDPOINT_URL': 'http://minio.mlops.svc.cluster.local:9000',
        'REDIS_HOST': 'redis-master.mlops.svc.cluster.local',
        'REDIS_PORT': '6379',
        'REDIS_DB': '2',
        'LLAMA_N_THREADS': '6',
    },
    container_resources=k8s.V1ResourceRequirements(
        requests={'cpu': '2', 'memory': '6Gi'},
        limits={'cpu': '6', 'memory': '10Gi'},
    ),
    secrets=[
        Secret('env', 'MLFLOW_TRACKING_USERNAME', 'mlflow-basic-auth-secret', 'username'),
        Secret('env', 'MLFLOW_TRACKING_PASSWORD', 'mlflow-basic-auth-secret', 'password'),
        Secret('env', 'AWS_ACCESS_KEY_ID', 'minio-secret', 'root-user'),
        Secret('env', 'AWS_SECRET_ACCESS_KEY', 'minio-secret', 'root-password'),
        Secret('env', 'REDIS_PASSWORD', 'redis-secret', 'redis-password'),
    ],
    dag=dag,
)

def log_end():
    print('Pipeline completed successfully. Check your MLflow Registry dashboard!')

end = PythonOperator(
    task_id='end',
    python_callable=log_end,
    dag=dag,
)

start >> gigaevo_train_and_register >> distill_intent_classifier >> end