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

# Get the latest release
LATEST_RELEASE=$(gcloud deploy releases list \
  --delivery-pipeline=$PIPELINE \
  --region=$REGION \
  --limit=1 \
  --format="value(name.basename())")

echo "🎯 Latest release: $LATEST_RELEASE"

# Monitor render phase
echo "🔄 Monitoring render phase..."
while true; do
  RENDER_STATE=$(gcloud deploy releases describe $LATEST_RELEASE \
    --delivery-pipeline=$PIPELINE \
    --region=$REGION \
    --format="value(renderState)")
  
  echo "   Render state: $RENDER_STATE"
  
  if [ "$RENDER_STATE" = "SUCCEEDED" ]; then
    echo "✅ Render phase completed successfully!"
    break
  elif [ "$RENDER_STATE" = "FAILED" ]; then
    echo "❌ Render phase failed!"
    exit 1
  fi
  
  sleep 10
done

# Monitor rollout
echo "🚀 Monitoring rollout..."
while true; do
  ROLLOUT_STATE=$(gcloud deploy rollouts list \
    --delivery-pipeline=$PIPELINE \
    --release=$LATEST_RELEASE \
    --region=$REGION \
    --limit=1 \
    --format="value(state)")
  
  echo "   Rollout state: $ROLLOUT_STATE"
  
  if [ "$ROLLOUT_STATE" = "SUCCEEDED" ]; then
    echo "✅ Rollout completed successfully!"
    break
  elif [ "$ROLLOUT_STATE" = "FAILED" ]; then
    echo "❌ Rollout failed!"
    exit 1
  fi
  
  sleep 10
done

# Get the Cloud Run service URL
SERVICE_URL=$(gcloud run services describe zergling-api \
  --region=$REGION \
  --format="value(status.url)")

echo "🌐 Service URL: $SERVICE_URL"

# Wait for Cloud Run service to be ready
echo "⏳ Waiting for Cloud Run service to be ready..."
sleep 30

# Test the health endpoint
echo "🏥 Testing health endpoint..."
MAX_RETRIES=10
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
  if curl -s -f "$SERVICE_URL/health" > /dev/null; then
    echo "✅ Health check passed!"
    break
  else
    echo "   Health check failed (attempt $((RETRY_COUNT + 1))/$MAX_RETRIES)"
    RETRY_COUNT=$((RETRY_COUNT + 1))
    sleep 10
  fi
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
  echo "❌ Health check failed after $MAX_RETRIES attempts"
  exit 1
fi

# Show final status
echo ""
echo "🎉 Deployment completed successfully!"
echo "📊 Final status:"
echo "   - Cloud Build: ✅ SUCCESS"
echo "   - Cloud Deploy Render: ✅ SUCCEEDED"
echo "   - Cloud Deploy Rollout: ✅ SUCCEEDED"
echo "   - Cloud Run Health: ✅ PASSED"
echo "🌐 Service URL: $SERVICE_URL" 