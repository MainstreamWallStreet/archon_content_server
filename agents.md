# Raven Agents Guide

This guide explains **how AI agents (and human contributors) should navigate, extend, and maintain Raven’s code‑base**.  Raven is a research assistant that fetches SEC filings & earnings‑call transcripts, reasons over the content with LLMs, and stores structured outputs in Google Drive.

---

## 1  Repository layout

| Path                          | Purpose                                                                                                                                                        |
| ----------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `src/api.py`                  | FastAPI service exposing a **job‑queue API**; jobs are throttled through a global `asyncio.Queue` and processed by one background worker fileciteturn1file2 |
| `src/edgar_cli.py`            | CLI + ETL pipeline that orchestrates Google Drive writes in a thread‑pool, calls the LLM pipeline, and prints cost summaries fileciteturn1file3             |
| `src/sec_filing.py`           | Locates the “cleanest” HTML artifact for a 10‑Q/10‑K, respecting the **1 req / sec SEC rule** fileciteturn1file0                                            |
| `src/transcript_helper.py`    | Fetches earnings‑call transcripts via API Ninjas and streams them into Docs fileciteturn1file4                                                              |
| `src/llm_reasoner.py`         | Async wrapper around GPT‑4 models with token & request limiters fileciteturn1file10                                                                         |
| `Dockerfile`, `skaffold.yaml` | Reproducible container + Cloud Run deploy pipeline fileciteturn1file9                                                                                       |
| `temp/`, `logs/`              | Ephemeral artefacts and debug logs – **never commit**.                                                                                                         |

> **Rule‑of‑thumb:** new functionality lives in `src/`; helper scripts can go in `tools/` (not yet present) until they deserve promotion.

---

## 2  Coding conventions

* **Python ≥ 3.11** with full typing.  Use **PEP 484** type hints everywhere.
* Format with **Black** (`black .`) and lint with **Ruff** (`ruff .`).
* Names:

  * `snake_case` for functions & variables.
  * `PascalCase` for classes.
  * `UPPER_SNAKE_CASE` for constants and env keys.
* All public functions/classes need **Google‑style docstrings**; include “Returns / Raises”.
* Prefer **async** for I/O; heavy CPU work may be off‑loaded with `asyncio.to_thread` fileciteturn1file14.

---

## 3  Concurrency & rate‑limits

| External service    | Guard                                                                   |
| ------------------- | ----------------------------------------------------------------------- |
| SEC EDGAR           | `_get()` enforces ≥ 1 s between requests fileciteturn1file0          |
| Google Drive / Docs | ThreadPoolExecutor capped by `GDRIVE_MAX=1` fileciteturn1file18      |
| OpenAI LLM          | `RateLimiter(rpm, tpm)` inside `llm_reasoner.py` fileciteturn1file10 |

AI agents **must preserve or improve these limits** when refactoring.

---

## 4  Environment & secrets

Raven relies on runtime config via `src/config.get_setting()`.

```
# .env.example
OPENAI_API_KEY=sk-…
TOKEN={…Google OAuth JSON…}
GOOGLE_DRIVE_ROOT_FOLDER_ID=…
API_NINJAS_KEY=…
FFS_API_KEY=local‑dev‑token   # FastAPI auth header X‑API-Key
LLM_MAX_RPM=200
LLM_MAX_TPM=40000
```

* **Never** hard‑code secrets.  Test code should stub `get_setting()`.

---

## 5  Local development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export $(grep -v "^#" .env | xargs)
uvicorn run_api:app --reload  # FastAPI service
python -m src.edgar_cli --ticker AAPL --year 2024 --quarter 1  # CLI mode
```

Run tests with **pytest**:

```bash
pytest -q        # fast
pytest --cov=src # coverage
```

---

## 6  Deployment

The container is built by Skaffold and deployed to Cloud Run:

```bash
skaffold run                 # local build → Cloud Run
skaffold dev --port-forward  # hot‑reload against live service
```

> **Tip:** Cloud Deploy injects `PROJECT_ID`; keep `region` in `skaffold.yaml` up to date.

---

## 7  Extending the system – task list for AI agents

| Area         | “Easy win” issues                                                                       |
| ------------ | --------------------------------------------------------------------------------------- |
| Filing fetch | Cache `ticker → CIK` mapping to avoid hitting SEC endpoint each run.                    |
| API          | Support **batch tickers** (`/batch/process`) returning one job per (ticker, year, qtr). |
| LLM          | Detect and skip duplicate tables; aggregate cost stats across API runs.                 |
| Storage      | Write structured tables to **BigQuery** in addition to Google Docs.                     |
| Monitoring   | Add `/metrics` Prometheus endpoint; expose queue length & job durations.                |

When opening a PR, create or update **unit tests**, and include a `CHANGELOG.md` entry.

---

## 8  Commit & PR guidelines

* **Conventional commits** (`feat:`, `fix:`, `chore:`…).
* Keep PRs < 400 loc when possible and focused on a single concern.
* CI must pass: `ruff`, `black --check`, `pytest`, and **type‑check** with `mypy --strict`.

---

## 9  Style cheatsheet for AI code suggestions

* Use `async with aiohttp.ClientSession()` for new HTTP integrations.
* When talking to Docs API, create **single batch updates** rather than many single‑call writes.
* Always funnel jobs through the global queue—even for CLI additions—so that rate‑limits stay central.

---

### Remember

Raven’s value is *precision + politeness*.  Respect external APIs, write defensively, and leave **clear logs** so that humans (and future agents) can trace what happened.
