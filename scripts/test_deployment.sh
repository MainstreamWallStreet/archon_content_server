#!/bin/bash
set -e

echo "🚀 Testing Zergling Cloud Deploy Pipeline..."

# Set variables
PROJECT_ID="mainstreamwallstreet"
REGION="us-central1"
PIPELINE="zergling-pipeline"
TARGET="dev"

# Get the current commit SHA
COMMIT_SHA=$(git rev-parse --short HEAD)
echo "📝 Using commit SHA: $COMMIT_SHA"

# Build and deploy using Cloud Build
echo "🔨 Starting Cloud Build..."
gcloud builds submit \
  --project=$PROJECT_ID \
  --config=cloudbuild.yaml \
  .

echo "✅ Cloud Build completed successfully!"

# Wait for the release to be created
echo "⏳ Waiting for Cloud Deploy release to be created..."
sleep 10

# List recent releases
echo "📋 Recent releases:"
gcloud deploy releases list \
  --delivery-pipeline=$PIPELINE \
  --region=$REGION \
  --limit=5

# Get the latest release
LATEST_RELEASE=$(gcloud deploy releases list \
  --delivery-pipeline=$PIPELINE \
  --region=$REGION \
  --limit=1 \
  --format="value(name.basename())")

echo "🎯 Latest release: $LATEST_RELEASE"

# Check the rollout status
echo "📊 Rollout status:"
gcloud deploy rollouts list \
  --delivery-pipeline=$PIPELINE \
  --release=$LATEST_RELEASE \
  --region=$REGION

echo "✅ Deployment pipeline test completed!"
echo "🌐 Service URL: https://zergling-api-455624753981.us-central1.run.app" 