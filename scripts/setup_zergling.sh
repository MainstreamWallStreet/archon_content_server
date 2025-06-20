#!/bin/bash
set -e

echo "🚀 Setting up Zergling FastAPI Server Template..."

# 1. Check for Terraform
if ! command -v terraform &> /dev/null; then
  echo "Terraform not found. Installing..."
  brew install terraform || (echo "Please install Terraform manually." && exit 1)
fi

# 2. Handle GCP credentials
CRED_PATH="gcp-service-account.json"
echo -e "\n== GCP Service Account Setup =="
if [ ! -f "$CRED_PATH" ]; then
  echo "Creating mock GCP service account for local testing..."
  cat > "$CRED_PATH" << 'EOF'
{
  "type": "service_account",
  "project_id": "mock-project",
  "private_key_id": "mock-key-id",
  "private_key": "-----BEGIN PRIVATE KEY-----\nMOCK_PRIVATE_KEY\n-----END PRIVATE KEY-----\n",
  "client_email": "mock@mock-project.iam.gserviceaccount.com",
  "client_id": "123456789",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/mock%40mock-project.iam.gserviceaccount.com"
}
EOF
  echo "Created mock $CRED_PATH for local testing"
  echo "⚠️  Note: For production, replace this with real GCP credentials"
else
  echo "Found existing $CRED_PATH"
fi

# 3. Set default values for API key and bucket
ZERGLING_API_KEY=${ZERGLING_API_KEY:-"test-api-key-$(date +%s)"}
EXAMPLE_BUCKET=${EXAMPLE_BUCKET:-"example_bucket"}

echo -e "\n== Environment Setup =="
echo "Using API Key: $ZERGLING_API_KEY"
echo "Using Bucket: $EXAMPLE_BUCKET"

# 4. Write .env
cat > .env <<EOF
ZERGLING_API_KEY=$ZERGLING_API_KEY
EXAMPLE_BUCKET=$EXAMPLE_BUCKET
GOOGLE_APPLICATION_CREDENTIALS=/app/$CRED_PATH
DEBUG=true
LOG_LEVEL=INFO
EOF

echo ".env written successfully."

# 5. Ensure .env and credentials are gitignored
if ! grep -q '^.env$' .gitignore; then echo ".env" >> .gitignore; fi
if ! grep -q "$CRED_PATH" .gitignore; then echo "$CRED_PATH" >> .gitignore; fi

# 6. Run tests first to ensure everything works
echo -e "\n== Running Tests =="
python -m pytest tests/ -v --tb=short

# 7. Build and run Docker
echo -e "\n== Building and Running Docker =="
docker build -t zergling:latest .

# Stop any existing container
docker stop zergling_test 2>/dev/null || true
docker rm zergling_test 2>/dev/null || true

# Run new container
docker run -d --rm \
  --env-file .env \
  -v "$(pwd)/$CRED_PATH:/app/$CRED_PATH" \
  -p 8080:8080 \
  --name zergling_test \
  zergling:latest

# 8. Wait for FastAPI to be ready
echo -e "\n== Waiting for FastAPI to start =="
for i in {1..30}; do
  if curl -s http://localhost:8080/health | grep -q '"status"'; then
    echo -e "\n✅ Zergling FastAPI is up and running!"
    echo "📝 API Documentation: http://localhost:8080/docs"
    echo "🔍 Health Check: http://localhost:8080/health"
    echo "🔑 API Key: $ZERGLING_API_KEY"
    echo -e "\n🎉 Setup complete! Your Zergling FastAPI server is ready."
    exit 0
  fi
  echo -n "."
  sleep 1
done

echo -e "\n❌ ERROR: FastAPI did not become ready in time."
echo "Check container logs:"
docker logs zergling_test
exit 1 