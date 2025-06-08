"""
src/config.py
=============

Centralised settings helper.

Lookup order
------------
1. Environment variables (including those loaded from an .env file).
2. Google Secret Manager   (only if GOOGLE_CLOUD_PROJECT is set).
3. Optional default passed to get_setting().

In Cloud Run we mount the secret as `/secrets/.env`; in local dev we look
for a project-root `.env`.  Either way, `python-dotenv` loads the file once
at import time and exposes the keys via `os.environ`, so the rest of the
codebase keeps calling `get_setting("KEY")` unchanged.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from google.cloud import secretmanager  # type: ignore
from dotenv import load_dotenv  # pip install python-dotenv


# ────────────────────────────────
# 🔐  Load .env (mounted or local)
# ────────────────────────────────
for _env in (Path("/secrets/.env"), Path(__file__).resolve().parent.parent / ".env"):
    if _env.exists():
        load_dotenv(_env, override=False)
        break


# ────────────────────────────────
# 🔑  Secret Manager client (lazy)
# ────────────────────────────────
@lru_cache(maxsize=None)
def _sm_client() -> secretmanager.SecretManagerServiceClient:
    return secretmanager.SecretManagerServiceClient()


# ────────────────────────────────
# 🎛️  Public helper
# ────────────────────────────────
def get_setting(
    name: str,
    *,
    secret_id: str | None = None,
    version: str = "latest",
    default: str | None = None,
) -> str:
    """
    Fetch a configuration value.

    Parameters
    ----------
    name : str
        Environment variable to look for.
    secret_id : str, optional
        Override the Secret Manager name (defaults to name in kebab-case).
    version : str, default "latest"
        Secret Manager version to fetch.
    default : str, optional
        Fallback value if nothing else is found.

    Returns
    -------
    str
        The requested setting.

    Raises
    ------
    RuntimeError
        If the setting is not found and no default is provided.
    """
    # 1️⃣  Immediate environment variable
    if val := os.getenv(name):
        return val

    # 2️⃣  GCP Secret Manager (only if running on GCP & IAM allows)
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCP_PROJECT")
    if project_id:
        sid = secret_id or name.lower().replace("_", "-")
        path = f"projects/{project_id}/secrets/{sid}/versions/{version}"
        try:
            resp = _sm_client().access_secret_version(name=path)
            return resp.payload.data.decode("utf-8")
        except Exception:
            pass  # fall through to default

    # 3️⃣  Default fallback
    if default is not None:
        return default

    raise RuntimeError(f"Missing required setting: {name}")
