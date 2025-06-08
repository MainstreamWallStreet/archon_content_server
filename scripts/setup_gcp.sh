#!/usr/bin/env bash
set -euo pipefail

# ─── configurable -----------------------------------------------------------------
PROJECT=mainstreamwallstreet
REGION=us-central1
REPO=raven-api                       # Artifact Registry repo
PIPELINE=raven-pipeline
TARGET=dev
SA=cloud-run-raven-sa               # service account Cloud Run uses
# -------------------------------------------------------------------------------

gcloud config set project "$PROJECT"

echo "🔑 enabling APIs…"
gcloud services enable run.googleapis.com artifactregistry.googleapis.com \
  clouddeploy.googleapis.com cloudbuild.googleapis.com secretmanager.googleapis.com \
  iam.googleapis.com

echo "🏗️  creating Artifact Registry (idempotent)…"
gcloud artifacts repositories create "$REPO" \
  --location="$REGION" --repository-format=docker \
  --description="Docker repo for Raven API" || true

echo "👤 service‑account + Secret Accessor role…"
gcloud iam service-accounts create "$SA" --display-name "Cloud Run Raven SA" || true
gcloud projects add-iam-policy-binding "$PROJECT" \
  --member="serviceAccount:$SA@$PROJECT.iam.gserviceaccount.com" \
  --role='roles/secretmanager.secretAccessor' --quiet

echo "🚚 Cloud Deploy pipeline & target…"
gcloud deploy apply --file clouddeploy/pipeline.yaml --region "$REGION"
gcloud deploy apply --file clouddeploy/targets/$TARGET.yaml --region "$REGION"

echo "🔐 bootstrapping secrets…"
# three API keys already exist – only add .env + client_secret if missing
for S in raven-env client_secret.json token.json ; do
  [[ -f "$S" ]] || continue      # skip if file absent
  ( gcloud secrets describe "$S" >/dev/null 2>&1 ) \
    || gcloud secrets create "$S" --data-file="$S"
done

echo "✅  Bootstrap done.  Commit & push the YAML below; Cloud Build will take it from there."
