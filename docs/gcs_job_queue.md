# GCS-backed Job Queue

This project now stores pending jobs in Google Cloud Storage so that work
survives restarts and multiple services can enqueue jobs.

## Bucket Setup

1. Create a bucket in your project:
   ```bash
   gsutil mb gs://<bucket-name>
   ```
2. Grant the Cloud Run service account write access:
   ```bash
   gsutil iam ch serviceAccount:<service-account>:roles/storage.objectAdmin gs://<bucket-name>
   ```
3. Add `JOB_QUEUE_BUCKET=<bucket-name>` to your `.env` file or Secret Manager.

## Local Development

Without GCS credentials the queue falls back to `temp/job_queue/` on disk.
Remove any files in that directory to clear the queue between runs.

## How It Works

Each job is stored as a JSON file under `jobs/` in the bucket. Fields include
`origin`, timestamps for received/started/completed, status and a run log. On
startup the API loads any queued jobs and schedules them for processing.
