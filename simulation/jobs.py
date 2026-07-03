from __future__ import annotations

"""In-memory background job manager for large tournament runs.

Small simulations run synchronously; large ones are submitted here so the
frontend can poll progress, then fetch the finished dataset for replay
(precompute-then-replay execution model).
"""

import threading
import time
import uuid
from typing import Callable


class Job:
    def __init__(self, job_id: str) -> None:
        self.id = job_id
        self.status = "pending"  # pending | running | done | error
        self.progress = 0.0
        self.error: str | None = None
        self.result_id: str | None = None
        self.created_at = time.time()

    def to_dict(self) -> dict:
        return {
            "job_id": self.id,
            "status": self.status,
            "progress": round(self.progress, 4),
            "error": self.error,
            "result_id": self.result_id,
        }


class JobManager:
    def __init__(self, max_results: int = 20) -> None:
        self._lock = threading.Lock()
        self._jobs: dict[str, Job] = {}
        self._results: dict[str, dict] = {}
        self._result_order: list[str] = []
        self._max_results = max_results

    def store_result(self, result: dict) -> str:
        result_id = uuid.uuid4().hex[:12]
        result["result_id"] = result_id
        with self._lock:
            self._results[result_id] = result
            self._result_order.append(result_id)
            while len(self._result_order) > self._max_results:
                evicted = self._result_order.pop(0)
                self._results.pop(evicted, None)
        return result_id

    def get_result(self, result_id: str) -> dict | None:
        with self._lock:
            return self._results.get(result_id)

    def get_job(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def submit(self, work: Callable[[Callable[[float], None]], dict]) -> Job:
        """Runs `work(progress_callback)` in a background thread; stores its dict result."""
        job = Job(uuid.uuid4().hex[:12])
        with self._lock:
            self._jobs[job.id] = job

        def set_progress(fraction: float) -> None:
            job.progress = fraction

        def runner() -> None:
            job.status = "running"
            try:
                result = work(set_progress)
                job.result_id = self.store_result(result)
                job.progress = 1.0
                job.status = "done"
            except Exception as exc:  # surfaced to the client via job status
                job.error = str(exc)
                job.status = "error"

        threading.Thread(target=runner, daemon=True).start()
        return job


JOB_MANAGER = JobManager()
