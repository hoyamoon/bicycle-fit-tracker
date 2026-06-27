#!/usr/bin/env bash
#
# Deploy / redeploy the FIT-parsing service to Cloud Run.
#
# This sets the flags that fix the failures seen from Make:
#   --allow-unauthenticated : the Make HTTP module calls with no auth, so the
#                             service must permit unauthenticated invocations
#                             (otherwise → 403 Forbidden).
#   --memory / --timeout    : give parsing of real ride files enough head-room
#                             so the worker is not killed mid-request
#                             (a killed worker is seen by the client as a
#                             503 "Service Unavailable" / ConnectionError).
#
# Usage (run from this directory):
#   ./deploy.sh
# Optionally override:
#   PROJECT_ID=my-project REGION=asia-northeast3 SERVICE=bycicle ./deploy.sh
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null)}"
REGION="${REGION:-asia-northeast3}"
SERVICE="${SERVICE:-bycicle}"

if [[ -z "${PROJECT_ID}" ]]; then
  echo "PROJECT_ID is not set and no default gcloud project is configured." >&2
  echo "Run: gcloud config set project <PROJECT_ID>   (or set PROJECT_ID=...)" >&2
  exit 1
fi

echo "Deploying '${SERVICE}' to project '${PROJECT_ID}' in '${REGION}'..."

gcloud run deploy "${SERVICE}" \
  --source . \
  --project "${PROJECT_ID}" \
  --region "${REGION}" \
  --allow-unauthenticated \
  --memory 512Mi \
  --cpu 1 \
  --timeout 300 \
  --concurrency 10 \
  --max-instances 3

echo "Done. Service URL:"
gcloud run services describe "${SERVICE}" \
  --project "${PROJECT_ID}" --region "${REGION}" \
  --format 'value(status.url)'
