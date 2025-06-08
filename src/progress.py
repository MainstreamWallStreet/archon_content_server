"""Utilities for tracking fine-grained job progress."""

from __future__ import annotations

import threading
from typing import Callable, Dict, Optional

# Mapping of job_id -> current short task description
job_tasks: Dict[str, str] = {}

_ctx = threading.local()
_message_cb: Optional[Callable[[str, str], None]] = None
_IGNORED_TASKS = {
    "paragraph",
    "write_para",
    "csv",
    "table",
    "write_header",
}


def bind_job(job_id: str) -> None:
    """Bind subsequent :func:`report` calls to ``job_id``."""
    _ctx.job_id = job_id


def current_job() -> Optional[str]:
    return getattr(_ctx, "job_id", None)


def clear_job() -> None:
    job_id = getattr(_ctx, "job_id", None)
    if job_id is not None:
        job_tasks.pop(job_id, None)
        delattr(_ctx, "job_id")


def set_message_callback(cb: Callable[[str, str], None]) -> None:
    """Register callback invoked on every :func:`report` call."""
    global _message_cb
    _message_cb = cb


def report(task: str) -> None:
    """Record ``task`` for the current job, if any."""
    job_id = current_job()
    if job_id:
        job_tasks[job_id] = task
        if _message_cb and task not in _IGNORED_TASKS:
            _message_cb(job_id, task)
