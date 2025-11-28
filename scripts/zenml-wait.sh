#!/usr/bin/env bash
set -euo pipefail

: "${ZENML_SERVER_URL:=http://zenml_server:8237}"

echo "[zenml-wait] waiting for ZenML server at ${ZENML_SERVER_URL} ..."
for i in $(seq 1 60); do
  if curl -fsS "${ZENML_SERVER_URL}" >/dev/null 2>&1; then
    echo "[zenml-wait] ZenML server is up."
    exit 0
  fi
  sleep 2
done

echo "[zenml-wait] ERROR: ZenML server not reachable at ${ZENML_SERVER_URL} after timeout." >&2
exit 1
