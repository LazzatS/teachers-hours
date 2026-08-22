#!/usr/bin/env bash
set -e

PROJECT_ID="${PROJECT_ID:-teachers-hours-506217}"
REGION="${REGION:-europe-west1}"
SERVICE="teachers-hours"

adk deploy cloud_run \
  --project="$PROJECT_ID" \
  --region="$REGION" \
  --service_name="$SERVICE" \
  --with_ui \
  ./skill_agent

# Gemini 3.5 Flash isn't served from europe-west1, and ADK defaults
# GOOGLE_CLOUD_LOCATION to the deploy region. Point the model at global.
gcloud run services update "$SERVICE" \
  --region="$REGION" \
  --update-env-vars GOOGLE_CLOUD_LOCATION=global,GOOGLE_GENAI_USE_VERTEXAI=TRUE
