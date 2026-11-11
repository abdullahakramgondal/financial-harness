"""Background tasks. The deep analysis runs the chat agent with progress tracking and retries."""
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agent.chat import run_chat  # noqa: E402
from worker import store  # noqa: E402
from worker.celery_app import app  # noqa: E402


@app.task(bind=True, max_retries=2, name="worker.tasks.deep_analysis")
def deep_analysis(self, task_id: str, question: str):
    """Run a long analysis. Progress and the final result are saved with worker.store."""
    attempt = self.request.retries + 1
    store.write(task_id, status="RUNNING", attempt=attempt, progress=3, message="Worker started")

    def on_progress(pct: int, message: str):
        store.write(task_id, progress=pct, message=message)

    try:
        answer, tools = asyncio.run(
            run_chat([{"role": "user", "content": question}], on_progress=on_progress)
        )
    except Exception as exc:
        if self.request.retries < self.max_retries:
            store.write(
                task_id,
                status="RETRYING",
                message=f"Attempt {attempt} failed: {exc}. Retrying in 5 seconds...",
            )
            raise self.retry(exc=exc, countdown=5)
        store.write(task_id, status="FAILED", error=str(exc), message="Failed after all retries")
        raise

    store.write(
        task_id, status="DONE", progress=100, message="Done", answer=answer, tools=tools
    )
    return task_id