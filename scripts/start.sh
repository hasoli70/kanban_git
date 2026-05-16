#!/usr/bin/env bash
set -euo pipefail

# Run from the project root.
if [[ ! -f Dockerfile ]]; then
  echo "error: run this script from the project root (Dockerfile not found)" >&2
  exit 1
fi

IMAGE=pm-app
CONTAINER=pm-app

if [[ ! -f .env ]]; then
  echo "error: .env not found in project root. Copy .env.example to .env first." >&2
  exit 1
fi

mkdir -p data

echo "Building image ${IMAGE}..."
docker build -t "${IMAGE}" .

if docker ps -a --format '{{.Names}}' | grep -qx "${CONTAINER}"; then
  echo "Removing existing container ${CONTAINER}..."
  docker rm -f "${CONTAINER}" >/dev/null
fi

echo "Starting container ${CONTAINER}..."
docker run -d \
  --name "${CONTAINER}" \
  -p 8000:8000 \
  --env-file .env \
  -v "$(pwd)/data:/app/data" \
  "${IMAGE}" >/dev/null

echo -n "Waiting for healthcheck"
for _ in $(seq 1 60); do
  status=$(docker inspect --format '{{.State.Health.Status}}' "${CONTAINER}" 2>/dev/null || echo "starting")
  if [[ "${status}" == "healthy" ]]; then
    echo
    echo "Container is healthy. App available at http://localhost:8000/"
    exit 0
  fi
  if [[ "${status}" == "unhealthy" ]]; then
    echo
    echo "error: container reported unhealthy" >&2
    docker logs "${CONTAINER}" --tail 50 >&2 || true
    exit 1
  fi
  echo -n "."
  sleep 2
done

echo
echo "error: timeout waiting for healthy status" >&2
docker logs "${CONTAINER}" --tail 50 >&2 || true
exit 1
