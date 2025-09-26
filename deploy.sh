#!/bin/bash

# Get project ID from gcloud config
PROJECT_ID=$(gcloud config get-value project)
SERVICE_NAME="neighbor-search"
REGION="us-central1"

# Build the Docker image
echo "Building Docker image..."
docker build -t gcr.io/$PROJECT_ID/$SERVICE_NAME .

# Push to Google Container Registry
echo "Pushing to Google Container Registry..."
docker push gcr.io/$PROJECT_ID/$SERVICE_NAME

# Deploy to Cloud Run
echo "Deploying to Cloud Run..."
gcloud run deploy $SERVICE_NAME \
  --image gcr.io/$PROJECT_ID/$SERVICE_NAME \
  --platform managed \
  --region $REGION \
  --allow-unauthenticated \
  --port 8080 \
  --memory 1Gi \
  --cpu 1 \
  --max-instances 10

echo "Deployment complete! Service URL:"
gcloud run services describe $SERVICE_NAME --region $REGION --format 'value(status.url)'
