#!/usr/bin/env sh
set -eu
BACKEND_URL="${BACKEND_URL:-http://localhost:8000/health}"
FRONTEND_URL="${FRONTEND_URL:-http://localhost:8080/}"
curl --fail --silent --show-error "$BACKEND_URL"
printf '\n'
curl --fail --silent --show-error --output /dev/null "$FRONTEND_URL"
printf 'Backend and frontend health checks passed.\n'
