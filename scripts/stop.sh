#!/usr/bin/env bash
set -euo pipefail

CONTAINER=pm-app

if docker ps -a --format '{{.Names}}' | grep -qx "${CONTAINER}"; then
  docker stop "${CONTAINER}" >/dev/null 2>&1 || true
  docker rm "${CONTAINER}" >/dev/null 2>&1 || true
  echo "Stopped and removed ${CONTAINER}."
else
  echo "Container ${CONTAINER} is not running."
fi
