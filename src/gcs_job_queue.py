from __future__ import annotations

import json
from datetime import datetime
from typing import Dict, List, Any, Optional

from google.cloud import storage
from google.cloud.exceptions import GoogleCloudError


class GcsJobQueue:
    """Persist job metadata in GCS with versioning and race condition handling."""

    def __init__(self, bucket: str, *, prefix: str = "jobs/") -> None:
        if not bucket:
            raise ValueError("GCS bucket name is required")
        self.bucket_name = bucket
        self.prefix = prefix
        try:
            # Initialize default GCS client (no emulator override)
            self._client = storage.Client()
            self._bucket = self._client.bucket(bucket)
            # Verify bucket exists and is accessible
            if not self._bucket.exists():
                raise ValueError(f"GCS bucket {bucket} does not exist")
        except GoogleCloudError as e:
            raise RuntimeError(f"Failed to initialize GCS client: {str(e)}")

    # ───────────────────────── private helpers ──────────────────────────
    def _blob_name(self, job_id: str) -> str:
        """Get the GCS blob name for a job."""
        return f"{self.prefix}{job_id}.json"

    def _load_job(self, job_id: str) -> Optional[Dict]:
        """Load a job from GCS, returning None if not found."""
        try:
            blob = self._bucket.blob(self._blob_name(job_id))
            exists = getattr(blob, "exists", lambda: False)()
            if not exists:
                return None
            raw = blob.download_as_text()
            if not isinstance(raw, (str, bytes, bytearray)):
                return None
            return json.loads(raw)
        except GoogleCloudError as e:
            raise RuntimeError(f"Failed to load job {job_id} from GCS: {str(e)}")

    def _save_job(self, job_id: str, data: Dict) -> None:
        """Save a job to GCS, ensuring atomic write."""
        try:
            # Ensure version is present
            if "version" not in data:
                data["version"] = 1

            # Convert to JSON with consistent formatting
            payload = json.dumps(data, sort_keys=True)

            # Upload to GCS
            blob = self._bucket.blob(self._blob_name(job_id))
            blob.upload_from_string(payload)
        except GoogleCloudError as e:
            raise RuntimeError(f"Failed to save job {job_id} to GCS: {str(e)}")

    # ───────────────────────── public API ──────────────────────────────
    def create_job(
        self, job_id: str, request: Dict[str, Any], point_of_origin: str
    ) -> Dict[str, Any]:
        """Create a new job in GCS with versioning."""
        # Check if job already exists
        if self._load_job(job_id) is not None:
            raise ValueError(f"Job {job_id} already exists in GCS")

        # Create job with version
        job = {
            "job_id": job_id,
            "request": request,
            "status": "queued",
            "time_received": datetime.utcnow().isoformat(),
            "time_started": None,
            "time_completed": None,
            "log": [],
            "point_of_origin": point_of_origin,
            "version": 1,
            "transcript_url": None,
            "transcript_date": None,
        }

        # Save to GCS
        self._save_job(job_id, job)
        return job

    def list_jobs(self) -> List[Dict]:
        """List all jobs from GCS, handling missing files gracefully."""
        try:
            jobs: List[Dict] = []
            for blob in self._client.list_blobs(self.bucket_name, prefix=self.prefix):
                try:
                    # Re-fetch the blob *without* the generation attribute to avoid
                    # stale-generation 404 errors (object was overwritten or deleted
                    # after list_blobs() returned).
                    fresh_blob = self._bucket.blob(blob.name)

                    # Attempt to download the latest data. If the object truly no longer
                    # exists we will get a NotFound error which we treat as a benign
                    # race-condition and simply skip.
                    raw = fresh_blob.download_as_text()

                    # Parse JSON payload
                    data = json.loads(raw)

                    # Ensure version is present for backwards-compatibility
                    if "version" not in data:
                        data["version"] = 1

                    jobs.append(data)
                except (GoogleCloudError, json.JSONDecodeError) as e:
                    # Log error but continue processing other jobs – a deleted or
                    # corrupt object should not break the entire listing.
                    print(f"Error loading job {blob.name}: {str(e)}")
            return jobs
        except GoogleCloudError as e:
            raise RuntimeError(f"Failed to list jobs from GCS: {str(e)}")

    def update_job(self, job_id: str, **kwargs) -> None:
        """Update job metadata in GCS, ensuring version field."""
        job = self._load_job(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found in GCS")

        # Update fields
        for key, value in kwargs.items():
            job[key] = value

        # Save back to GCS
        self._save_job(job_id, job)

    def append_log(self, job_id: str, message: str) -> None:
        """Append a log message to a job, ensuring atomic update."""
        job = self._load_job(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found in GCS")

        # Append log message
        job.setdefault("log", []).append(
            {"ts": datetime.utcnow().isoformat(), "msg": message}
        )

        # Save back to GCS
        self._save_job(job_id, job)
