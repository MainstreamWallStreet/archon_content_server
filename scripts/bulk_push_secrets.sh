#!/usr/bin/env bash
#
# bulk_push_secrets.sh
# --------------------
# Read KEY=VALUE lines from stdin **or** from a .env-style file and:
#   1. Create the secret in Secret Manager if it does not exist.
#   2. Add the value as a new secret version.
#
# Usage examples
# --------------
#   # Pipe a here-doc (like the one you tested):
#   ./bulk_push_secrets.sh <<'EOF'
#   FOO=bar
#   BAR=baz
#   EOF
#
#   # Push everything that’s in .env
#   ./bulk_push_secrets.sh < .env
#
#   # Explicit project id (default = `gcloud config get-value project`)
#   GCP_PROJECT=my-project ./bulk_push_secrets.sh < .env
#
set -euo pipefail

GCP_PROJECT="${GCP_PROJECT:-$(gcloud config get-value --quiet project)}"

if [[ -z "${GCP_PROJECT}" ]]; then
  echo "❌  No project configured (GCP_PROJECT env var empty and gcloud default not set)." >&2
  exit 1
fi

echo "ℹ️  Using project: ${GCP_PROJECT}"
echo

while IFS='=' read -r NAME VALUE || [[ -n "${NAME}" ]]; do
  # Skip blank lines / comments
  [[ -z "${NAME}" || "${NAME}" =~ ^[[:space:]]*# ]] && continue

  NAME="$(echo -n "${NAME}" | xargs)"          # trim
  VALUE="$(echo -n "${VALUE}" | sed 's/^[[:space:]]*//')" # left-trim value

  if [[ -z "${VALUE}" ]]; then
    echo "⚠️  Skipping '${NAME}' (empty value)"
    continue
  fi

  # 1️⃣  Create the secret if it doesn't exist
  if ! gcloud secrets describe "${NAME}" --project="${GCP_PROJECT}" >/dev/null 2>&1; then
    echo "➕  Creating secret '${NAME}'"
    gcloud secrets create "${NAME}" \
      --project="${GCP_PROJECT}" \
      --replication-policy="automatic" \
      --quiet
  else
    echo "🔄  Secret '${NAME}' already exists – adding new version"
  fi

  # 2️⃣  Add the value as a new version
  printf '%s' "${VALUE}" | \
    gcloud secrets versions add "${NAME}" \
      --project="${GCP_PROJECT}" \
      --data-file=- \
      --quiet

done

echo
echo "✅  Done."
