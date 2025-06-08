#!/usr/bin/env bash
#
# manage_secrets.sh ─ simple wrapper around gcloud Secret Manager
#
#  USAGE
#    ./manage_secrets.sh create   SECRET_NAME [--value=<plaintext>|--file=<path>]
#    ./manage_secrets.sh update   SECRET_NAME [--value=<plaintext>|--file=<path>]
#    ./manage_secrets.sh bind     SECRET_NAME SERVICE_ACCOUNT          # grant roles/secretmanager.secretAccessor
#    ./manage_secrets.sh delete   SECRET_NAME                           # removes the secret entirely
#    ./manage_secrets.sh list                                              # lists all secrets
#
#  ENV
#    PROJECT_ID   (defaults to currently configured project)
#
#  EXAMPLES
#    ./manage_secrets.sh create  ffs-api-key  --value='sk_raven_…c0fc'
#    ./manage_secrets.sh bind    ffs-api-key  cloud-run-ffs-sa@mainstreamwallstreet.iam.gserviceaccount.com
#
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project)}"
[[ -z "$PROJECT_ID" ]] && { echo "👉  PROJECT_ID not set; run 'gcloud config set project <id>'"; exit 1; }

die() { echo "❌  $*"; exit 1; }

cmd="${1:-}"
shift || true

get_payload() {
  local value file
  for arg in "$@"; do
    case "$arg" in
      --value=*) value="${arg#*=}" ;;
      --file=*)  file="${arg#*=}"  ;;
    esac
  done
  [[ -n "${value:-}" && -n "${file:-}" ]] && die "Use --value OR --file, not both"
  if [[ -n "${value:-}" ]]; then
    printf '%s' "$value"
  elif [[ -n "${file:-}" ]]; then
    [[ -r "$file" ]] || die "File '$file' not found or unreadable"
    cat "$file"
  else
    # read from stdin if neither flag given
    cat
  fi
}

case "$cmd" in
  create)
    secret="$1"; shift
    if gcloud secrets describe "$secret" >/dev/null 2>&1; then
      echo "ℹ️  Secret '$secret' already exists – using update instead."
      set -- update "$secret" "$@"
      exec "$0" "$@"
    fi
    payload="$(get_payload "$@")"
    echo "$payload" | \
      gcloud secrets create "$secret" \
        --data-file=- \
        --project="$PROJECT_ID"
    ;;

  update)
    secret="$1"; shift
    gcloud secrets describe "$secret" --project "$PROJECT_ID" >/dev/null 2>&1 \
      || die "Secret '$secret' does not exist – run create first."
    payload="$(get_payload "$@")"
    echo "$payload" | \
      gcloud secrets versions add "$secret" \
        --data-file=- \
        --project="$PROJECT_ID"
    ;;

  bind)
    [[ $# -eq 2 ]] || die "Usage: $0 bind SECRET_NAME SERVICE_ACCOUNT"
    secret="$1"
    sa="$2"
    gcloud secrets add-iam-policy-binding "$secret" \
      --member="serviceAccount:${sa}" \
      --role="roles/secretmanager.secretAccessor" \
      --project="$PROJECT_ID"
    ;;

  delete)
    secret="$1"
    read -rp "Really delete secret '$secret'? [y/N] " ans
    [[ "$ans" == [yY]* ]] || { echo "Aborted."; exit 0; }
    gcloud secrets delete "$secret" --quiet --project "$PROJECT_ID"
    ;;

  list|"")
    gcloud secrets list --project "$PROJECT_ID"
    ;;

  *)
    die "Unknown command: $cmd"
    ;;
esac
