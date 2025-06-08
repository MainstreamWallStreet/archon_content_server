# Changelog
<!-- ruff: noqa -->

## Unreleased
### Added
- `/updates` endpoint consolidating job and task status.
- Fine-grained progress messages now tracked per job and exposed via `/updates`.
- Jobs now store a `start_time` when queued.
- Design document for running up to four jobs concurrently while keeping a
  single queue.
- `task_queue` replaces `job_queue`; up to four workers run in parallel with
  automatic retries on failure.
- Integration test verifies that fifty queued jobs finish using a stubbed worker.
- CI now runs against a lightweight GCS emulator with no service-account creds required.
- Job queue now persists to Google Cloud Storage with per-job origin tracking.
- Quarterly data version tracking with `QUARTERLY_FILING_DATA_VERSION` and
  `TRANSCRIPT_DATA_VERSION` now added to docs as `data_version = n`.
- Google Drive storage now creates a `Q<quarter>` folder within each year
  folder, and document titles follow `TICKER YYYY QN - <doctype>`.
- **GCS-backed job queue:**
  - All job metadata is now stored in a Google Cloud Storage bucket, ensuring persistence across server restarts and enabling multiple services to enqueue jobs.
  - On startup, the API loads any queued jobs from GCS and schedules them for processing.
  - Each job is stored as a JSON file under `jobs/` in the bucket, including fields for origin, status, timestamps, and a run log.
  - Local development falls back to `temp/job_queue/` if GCS credentials are not available.
  - See `docs/gcs_job_queue.md` for setup and details.
- **Test infrastructure improvements:**
  - `test_list_all_jobs` now properly cleans up the GCS bucket before running, ensuring test isolation and reliability.
  - Added fixture logic to clear jobs and tasks before and after each test.
  - Added pytest-asyncio configuration for async test support.
### Removed
- Deprecated `/status/{job_id}`, `/jobs`, `/stream/jobs`, and `/stream/tasks` endpoints.

### Fixed
- Avoid duplicate company folders when processing multiple quarters concurrently.
- Google Docs operations now use exponential backoff with retries.
- Documents now saved under ``{ticker}/{year}`` folders in Drive.
- Pytest and lint configuration fixed to allow local testing.
- Table rows returned as dicts are now expanded correctly.
- OpenAI calls now retry on transient errors.
- Quarter processing continues after individual failures.
- **Test reliability:**
  - Fixed `test_list_all_jobs` to avoid counting jobs from previous runs by cleaning up the GCS bucket and using unique origins.
  - Updated Pydantic model usage to use `model_dump()` instead of deprecated `dict()` method.
  - `/updates` now drops in-memory jobs missing from the GCS bucket so deleted jobs don't reappear.
  - Invalid or missing `TOKEN` secrets no longer crash job workers.
  - TOKEN values with trailing characters are parsed correctly.
  - Tests mock Google clients without requiring the real packages.
  - Fixed GCS job listing to handle race conditions gracefully. When listing jobs, if an object is deleted or overwritten between listing and reading, the code now re-fetches the blob without the generation attribute to avoid 404 errors. This prevents noisy error logs when jobs are deleted or updated concurrently.
  - 10-Q/10-K documents are now saved with the correct form in their title.
  - Added a regression test ensuring transcript docs don't replace the quarterly filing.
  - Jobs now fail if filing processing raises an exception.
  - A background status printer now logs each job's phase every 10s, showing transcript and filing completion links.
  - Verbose paragraph-level progress logs are suppressed.

