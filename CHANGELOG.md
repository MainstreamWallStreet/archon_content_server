# Changelog
<!-- ruff: noqa -->

## [2025-01-10] - Instant Earnings Data Loading
### Added
- **Public Earnings Endpoint**: New `/public/earnings/upcoming` endpoint that provides upcoming earnings data without authentication
- **Immediate Data Loading**: Website now loads upcoming earnings calls asynchronously when first rendered, even before user authentication
- **Smart Caching**: Earnings data is cached in localStorage for instant display on subsequent visits
- **Seamless Experience**: Data is pre-loaded on login page and immediately available when user accesses dashboard

### Changed
- **Enhanced User Experience**: Users can now see upcoming earnings calls immediately upon visiting the site, without waiting for login
- **Optimized Loading Strategy**: 
  - Login page: Preloads and caches earnings data in background
  - Dashboard: Displays cached data instantly, then refreshes with fresh data
  - Authenticated users: Still use secured endpoints for data modification operations
- **Dual Endpoint Strategy**: Maintains both public (read-only) and authenticated (full-access) endpoints for optimal security and performance

### Technical
- Public endpoint mirrors authenticated endpoint functionality but without API key requirement
- Intelligent fallback system: tries authenticated endpoint first for logged-in users, falls back to public for unauthenticated access
- Data consistency maintained between public and authenticated endpoints
- Zero-downtime experience with cached data and background refresh

## [2025-01-10] - API Ninjas Integration Optimization
### Changed
- **Optimized API Field Handling**: Updated earnings API integration to align with official API Ninjas documentation:
  - Now prioritizes the official `date` field as documented in API Ninjas earnings calendar API
  - Improved field priority order: `date`, `earnings_date`, `announcement_date`, `report_date`, `call_date`, `earnings_call_date`
  - Enhanced API call strategy prioritizing `show_upcoming=true` as the primary method
- **Better API Documentation Compliance**: API calls now follow the official API Ninjas structure and response format
- **Improved Data Structure Validation**: More robust handling of API response fields according to official documentation

### Technical Notes
- The underlying data quality limitations of API Ninjas (outdated/stale earnings schedules) persist
- API correctly returns `date` field with proper structure but contains far-future dates (2025-2027) instead of near-term earnings
- Implementation now properly follows official API Ninjas documentation for maximum compatibility

## [2025-01-10] - Earnings Monitoring System Overhaul
### Added
- **Refresh Button for Upcoming Earnings**: Added a refresh button to the web UI's "Upcoming Calls" tab that manually triggers data refresh
- **Comprehensive Earnings Data Logging**: Extremely detailed logging for every step of the earnings refresh process, showing:
  - API requests and responses for each ticker
  - Date field detection and parsing attempts
  - GCS storage operations with exact file paths
  - Email queue generation with timestamps and locations
- **Robust Date Field Fallbacks**: System now tries multiple date field names when parsing API responses:
  - `earnings_date`, `date`, `announcement_date`, `report_date`, `call_date`, `earnings_call_date`
- **Multiple API Endpoint Fallbacks**: If the primary API endpoint fails, automatically tries alternative endpoints:
  - Primary: `/earningscalendar?ticker=X&show_upcoming=true`
  - Fallback: `/earningscalendar?ticker=X` (all earnings data)
- **Smart Date Parsing**: Handles multiple date formats including:
  - Date-only strings (`2026-04-13`) with assumed market close time
  - ISO format with Z timezone (`2026-04-13T21:00:00Z`)
  - Timezone-aware datetime objects
- **GCS-Based Earnings Display**: UI now reads upcoming earnings from GCS storage instead of making live API calls

### Changed
- **Simplified Email Notifications**: Removed one-hour notifications since API only provides dates, not specific times
- **Earnings Data Source**: `/earnings/upcoming` endpoint now reads from GCS storage for faster, more reliable data access
- **Email Schedule Optimization**: Only sends meaningful notifications (one week before, day before) based on available date precision

### Fixed
- **Timezone Comparison Errors**: Fixed "can't compare offset-naive and offset-aware datetimes" errors by ensuring all datetime objects have proper timezone info
- **Missing Earnings Data in UI**: Resolved issue where earnings calls were saved to GCS but not displayed in the web interface
- **API Response Field Variations**: Handles cases where API returns different field names than expected
- **Date Format Inconsistencies**: Robust parsing for various date formats returned by the earnings API

## Unreleased
### Added
- **Enhanced Email Alert Logging**: Comprehensive logging now shows exactly which email addresses are receiving alerts, with detailed success/failure status for each recipient
- **Improved Alert Recipients Handling**: Better error handling and validation for the `ALERT_RECIPIENTS` array, ensuring all configured emails receive alerts
- **Secret Manager Integration**: Added `alert-recipients` secret in Terraform to properly handle the array of email addresses
- **Robust Error Recovery**: Alert system now continues sending to remaining recipients even if some emails fail
- SendGrid email helper for notifications.
- `ALERT_RECIPIENTS` env var supports multiple alert emails.
- Script `scripts/watchlist_demo.py` demonstrates adding and removing a ticker.
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
- Simple password-protected web UI for managing the watchlist.
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
- Open Graph and Twitter meta tags for social/share image using inline SVG logo matching the homepage dashboard icon. Now, sharing or texting the app link shows the Banshee logo as the preview image.
### Removed
- Deprecated `/status/{job_id}`, `/jobs`, `/stream/jobs`, and `/stream/tasks` endpoints.
- Legacy Raven tests replaced with Banshee-specific suite.

### Fixed
- Avoid duplicate company folders when processing multiple quarters concurrently.
- Google Docs operations now use exponential backoff with retries.
- Documents now saved under ``{ticker}/{year}`` folders in Drive.
- Pytest and lint configuration fixed to allow local testing.
- Table rows returned as dicts are now expanded correctly.
- OpenAI calls now retry on transient errors.
- Quarter processing continues after individual failures.
- GCS job queue tests updated and SendGrid mock added.
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
  - Terraform now provisions the `banshee-data` bucket and grants the Cloud Run
    service account `roles/run.invoker` and storage access.
  - Cloud Deploy release names now patch the correct container image.

