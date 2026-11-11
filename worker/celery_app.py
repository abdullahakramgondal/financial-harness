"""Celery app. Uses the filesystem broker so no Redis is needed (works on Windows).
For production, replace the broker with Redis or Amazon SQS.
Start the worker from the project root:
  celery -A worker.celery_app worker --pool=solo --loglevel=info --without-gossip --without-mingle --without-heartbeat
"""
from pathlib import Path

from celery import Celery

ROOT = Path(__file__).resolve().parent.parent
BROKER_DIR = ROOT / "broker"
for sub in ("queue", "processed"):
    (BROKER_DIR / sub).mkdir(parents=True, exist_ok=True)

app = Celery("harness", broker="filesystem://", include=["worker.tasks"])
app.conf.update(
    broker_transport_options={
        "data_folder_in": str(BROKER_DIR / "queue"),
        "data_folder_out": str(BROKER_DIR / "queue"),
        "processed_folder": str(BROKER_DIR / "processed"),
    },
    task_ignore_result=True,          # results are saved by worker/store.py instead
    worker_enable_remote_control=False,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
)