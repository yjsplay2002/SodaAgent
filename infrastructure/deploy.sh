#!/bin/bash
set -euo pipefail

# SodaAgent - One-command GCP deployment script
# Usage: ./infrastructure/deploy.sh

PROJECT_ID="soda-agent-hackathon"
REGION="${GOOGLE_CLOUD_LOCATION:-us-central1}"
SERVICE_NAME="soda-agent"
REPO_NAME="soda-agent-repo"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/${SERVICE_NAME}"

gcloud config set project "$PROJECT_ID"

echo "=== Deploying SodaAgent to Cloud Run ==="
echo "Project: $PROJECT_ID"
echo "Region:  $REGION"
echo ""

# 0. Ensure Artifact Registry repo exists
echo "[0/4] Ensuring Artifact Registry repository..."
gcloud artifacts repositories create "$REPO_NAME" \
    --repository-format=docker \
    --location="$REGION" \
    --project="$PROJECT_ID" 2>/dev/null || true

# 1. Build and push container image via Cloud Build
echo "[1/4] Building container image..."
gcloud builds submit \
    --project "$PROJECT_ID" \
    --tag "$IMAGE" \
    --timeout=600 \
    .

# 2. Deploy to Cloud Run
echo "[2/4] Deploying to Cloud Run..."
gcloud run deploy "$SERVICE_NAME" \
    --project "$PROJECT_ID" \
    --image "$IMAGE" \
    --region "$REGION" \
    --min-instances 1 \
    --max-instances 3 \
    --memory 1Gi \
    --cpu 2 \
    --timeout 3600 \
    --session-affinity \
    --allow-unauthenticated \
    --set-secrets "GOOGLE_API_KEY=google-api-key:latest" \
    --set-env-vars "GOOGLE_GENAI_USE_VERTEXAI=FALSE,GOOGLE_CLOUD_PROJECT=$PROJECT_ID,GOOGLE_CLOUD_LOCATION=$REGION"

# 3. Get the service URL
echo "[3/4] Getting service URL..."
SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" \
    --project "$PROJECT_ID" \
    --region "$REGION" \
    --format "value(status.url)")

echo "Service URL: $SERVICE_URL"

# 4. Health check
echo "[4/4] Health check..."
HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "${SERVICE_URL}/health" || echo "000")
if [ "$HTTP_STATUS" = "200" ]; then
    echo "✅ Health check passed!"
else
    echo "⚠️  Health check returned: $HTTP_STATUS (service may still be starting)"
fi

echo ""
echo "=== Deployment Complete ==="
echo "Service URL: $SERVICE_URL"
echo "Health:      $SERVICE_URL/health"
echo "WebSocket:   ${SERVICE_URL/https/wss}/ws/mobile/{user_id}"
