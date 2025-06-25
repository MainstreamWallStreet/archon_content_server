#!/bin/bash
set -e

echo "🚀 Testing Archon Content Direct Cloud Run Deployment..."

# Set variables
PROJECT_ID="mainstreamwallstreet"
REGION="us-central1"
SERVICE_NAME="archon-content-api"

# Get the current commit SHA
COMMIT_SHA=$(git rev-parse --short HEAD)
echo "📝 Using commit SHA: $COMMIT_SHA"

# Build and deploy using Cloud Build
echo "🔨 Starting Cloud Build..."
gcloud builds submit \
  --project=$PROJECT_ID \
  --config=cloudbuild.yaml \
  --substitutions=_REGION=$REGION,_SERVICE=$SERVICE_NAME \
  .

echo "✅ Cloud Build completed successfully!"

# Get the Cloud Run service URL
echo "🌐 Getting service URL..."
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME \
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
echo "   - Cloud Run Deployment: ✅ SUCCESS"
echo "   - Health Check: ✅ PASSED"
echo "🌐 Service URL: $SERVICE_URL" 