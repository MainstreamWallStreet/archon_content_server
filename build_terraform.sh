#!/bin/bash
set -e

PROJECT_ID=$(terraform output -raw project 2>/dev/null || echo "mainstreamwallstreet")
BUCKET_NAME=$(terraform output -raw example_bucket 2>/dev/null || echo "example_bucket")
REGION=$(terraform output -raw region 2>/dev/null || echo "us-central1")

# 1. Create GCS bucket for Terraform backend if it doesn't exist
echo "Checking for GCS bucket: $BUCKET_NAME..."
gsutil ls -b gs://$BUCKET_NAME >/dev/null 2>&1 || \
  gsutil mb -p $PROJECT_ID -l $REGION gs://$BUCKET_NAME

echo "GCS bucket ready: $BUCKET_NAME"

# 2. Terraform init
terraform init

# 3. Terraform plan
terraform plan

# 4. Terraform apply
echo "Applying Terraform..."
terraform apply -auto-approve

echo "Terraform infrastructure is ready!" 