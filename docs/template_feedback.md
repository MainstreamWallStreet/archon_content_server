# Template Feedback – Archon Content Server one-click deploy

_This document captures the friction points we hit while attempting an "out-of-the-box" deploy of the repo and proposes concrete template updates so the next consumer can provision Archon in a single command._

---

## 1. Build/Deploy pipeline

### 1.1 Missing Python entry-point detected by Cloud Build packs
* **Symptom:** Cloud Build failed with `Python – Missing Entrypoint`.
* **Root cause:** Build packs look for one of:
  * `main.py` exposing `app`
  * a `Procfile`
  * `GOOGLE_ENTRYPOINT` env var.
  None were present – template ships `run.py` (dev execution) only.
* **Fix applied in session:** created `main.py` that imports the FastAPI `app` and re-exports it, while still delegating to `run.main()` when executed locally.

### 1.2 Gunicorn couldn't import `app`
* **Symptom:** Service deployed but crashed (`Failed to find attribute 'app' in 'main'`). 503 on `/health`.
* **Root cause:** Our first `main.py` exposed only `main()`; gunicorn default command from build pack is `gunicorn -b :8080 main:app`.
* **Fix applied:** added
  ```py
  from src.api import app as fastapi_app
  app = fastapi_app
  ```

### Recommended template change
* Ship **one canonical entry-point** (`main.py`) that satisfies both local dev (`python run.py`) and build packs (`APP=main:app`).
* Alternatively add a **`Procfile`**:
  ```
  web: uvicorn src.api:app --host 0.0.0.0 --port 8080
  ```
  and commit. This removes the need for `main.py` entirely; uvicorn tends to start faster than gunicorn+uvicorn workers.

## 2. Terraform workflow

### 2.1 IAM resource references non-existent Cloud Run service
* **Symptom:** `terraform apply` aborted with
  `Resource 'archon-content-api' of kind 'SERVICE' … does not exist`.
* **Root cause:** Module only creates **IAM bindings** for a Cloud Run service assumed to pre-exist. The service itself is not part of Terraform and was not yet deployed manually.

### Recommended template changes
1. Add a **`google_cloud_run_service` (v1) or `google_cloud_run_v2_service`** resource in `infra/main.tf`.  Example snippet:
   ```hcl
   resource "google_cloud_run_v2_service" "archon" {
     name     = "archon-content-api"
     location = var.region

     template {
       containers {
         image = "${var.region}-docker.pkg.dev/${var.project}/archon-content/archon-content:latest"
         env {
           name  = "ARCHON_API_KEY"
           value_source {
             secret_key_ref {
               secret  = google_secret_manager_secret.archon_api_key.secret_id
               version = "latest"
             }
           }
         }
         ports { container_port = 8080 }
       }
       service_account = data.google_service_account.cloud_run_sa.email
       timeout         = "300s"
     }
   }
   ```
2. Change the IAM binding to reference `google_cloud_run_v2_service.archon.name` instead of hard-coding the string.
3. Document the prerequisite that the **container image must exist**.  A simple pattern is:
   * push image via Cloud Build (already in template's Cloud Build YAML),
   * run `terraform apply` which now creates Cloud Run service + IAM in one pass.

## 3. Secrets & configuration
* `.env` / `terraform.tfvars` hold placeholder secrets. Provide a **`sample.env` + commented tfvars example** with instructions on
  * generating a random 256-bit `ARCHON_API_KEY`,
  * adding provider API keys,
  * base-64 encoding the Google SA JSON for `google_sa_value`.
* Consider supplying a **helper script** (see below) that uploads these secrets to Secret Manager before first apply.

## 4. Helper scripts
Existing scripts (`scripts/*.sh`) handle local dev & tests but don't automate the cloud flow. Two small additions would close the gap:

| Script | Purpose |
|--------|---------|
| `scripts/build_image.sh` | `gcloud builds submit --pack image=$AR_IMAGE --project $PROJECT` (or docker build/push) |
| `scripts/deploy_all.sh`  | 1) call `build_image.sh`, 2) `terraform -chdir=infra apply -auto-approve` |

Both scripts can source a common `scripts/env.sh` that exports `PROJECT`, `REGION`, etc., from either `gcloud config` or a `.env`.

These would enable **one-click (one-command) deploy**:
```bash
./scripts/deploy_all.sh  # builds image & fully provisions infra
```

## 5. Documentation
* Update `docs/deployment/deploy.md` to reflect the new flow:
  1. Clone repo & run `./scripts/setup_local_dev.sh` (already exists).
  2. Export/enter project ID & region.
  3. Run **one command** as above.
* Mention minimum IAM roles required on the executing account (`roles/owner` or the individual sub-roles listed in Terraform).

## 6. Optional quality-of-life tweaks
* Add **pre-commit** hook to assert `terraform fmt -check` and that tests pass.
* Lift the Python runtime to 3.12 everywhere (already set in `.python-version` – ensure Cloud Build builder uses same version).
* Use **build arguments** or `ENV` in `Dockerfile` to allow devs to override log level without code edit.

---

### Summary checklist for next template version
- [ ] Provide `main.py` or `Procfile` exposing `app`.
- [ ] Incorporate Cloud Run service into Terraform.
- [ ] Add build + deploy helper scripts and document single-command usage.
- [ ] Clarify secrets bootstrap process.
- [ ] Refresh docs and sample environment files.

Making these adjustments means a fresh user can fork the repo, set four env-vars, run **one command**, and have a live Archon Content Server ready to use.  No more manual patch-ups! 🎉 