#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Run Langflow with project-local flows directory
# ---------------------------------------------------------------------------
# This helper starts Langflow so that all its data (database, logs, flows, …)
# live inside ./src/flows.  You can pass any additional arguments you would
# normally give to `langflow run` and they will be forwarded unchanged.
#
# Usage:
#   ./run_langflow.sh                          # normal startup
#   ./run_langflow.sh --backend-only --port 80 # with extra CLI flags
# ---------------------------------------------------------------------------
set -euo pipefail

# Absolute path to the repo root (directory containing this script)
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Directory where flows, DB and other Langflow artefacts will be stored
FLOW_DIR="$ROOT_DIR/src/flows"

# Ensure the directory exists so that Langflow can write to it
mkdir -p "$FLOW_DIR"

# Environment variables that tell Langflow to use FLOW_DIR
export LANGFLOW_CONFIG_DIR="$FLOW_DIR"
export LANGFLOW_LOAD_FLOWS_PATH="$FLOW_DIR"

# (Optional) Do not auto-open browser on startup
export LANGFLOW_OPEN_BROWSER="false"

# Start Langflow – forward all script arguments to `langflow run`
exec langflow run "$@" 