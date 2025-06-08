# Parallel Job Processing Design

This document outlines how Raven can process multiple jobs in parallel while retaining the
centralised `asyncio.Queue` for rate limiting and visibility.

## Goals

- Run up to **four jobs at the same time** so long-running filings do not block the queue.
- Keep a *single* queue so monitoring and rate limiting stay centralised.
- Surface running tasks through the `/updates` endpoint.

## Proposed Approach

1. **Queue Remains Global**
   - Incoming jobs are still placed into a single `task_queue`.
   - Jobs record a `start_time` when queued for later reference.

2. **Multiple Worker Tasks**
   - At startup, the API launches `MAX_CONCURRENT_JOBS` worker tasks (default `4`).
   - Each worker loops: `job_id, req = await task_queue.get()` then processes the job using the existing `_process` helper.
   - Workers run independently, so up to four jobs may execute simultaneously.
   - The `active_tasks` dictionary continues to track tasks per job for the `/updates` endpoint.

3. **Rate Limiting**
   - External API throttling (SEC, Google, OpenAI) still occurs inside `_process` and related helpers.
   - Having a single queue ensures new jobs are accepted only when a worker is free, preventing uncontrolled concurrency.

4. **Monitoring via `/updates`**
   - The endpoint already returns `user_requested_jobs` and `in_progress_server_tasks`.
   - With multiple workers, this payload will now show up to four running jobs concurrently.

## Configuration

- `MAX_CONCURRENT_JOBS` constant in `src/api.py` (optionally overridden by env variable) defines the number of workers.
- The rest of the API remains unchanged; clients simply see faster overall throughput.

## Future Considerations

- If more throughput is required, the constant can be increased after verifying external API limits.
- Adding `/metrics` to expose queue length and job durations would help monitor performance.
