FROM git.alexshishin.ru/mlops/training-base:latest

WORKDIR /app

COPY labels.json .
COPY examples.jsonl .
COPY augmented_train.jsonl .
COPY run_gigaevo_pipeline.py .
COPY distilled_intent_classifier.py .

CMD ["python", "run_gigaevo_pipeline.py"]
