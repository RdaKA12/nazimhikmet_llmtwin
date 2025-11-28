#!/usr/bin/env bash
set -euo pipefail

PORT=8237
LISTEN_OUTPUT=""

export ZENML_LOCAL_SERVER_HOST="${ZENML_LOCAL_SERVER_HOST:-0.0.0.0}"

echo "Checking for existing listeners on ${PORT}..."
if command -v ss >/dev/null 2>&1; then
    LISTEN_OUTPUT=$(ss -lntp | grep -F ":${PORT}" || true)
elif command -v netstat >/dev/null 2>&1; then
    LISTEN_OUTPUT=$(netstat -tlnp 2>/dev/null | grep -F ":${PORT}" || true)
else
    LISTEN_OUTPUT=$(ZENML_PORT="${PORT}" python - <<PY || true
import os
import socket
port = int(os.environ.get("ZENML_PORT", "8237"))
found = []
with open("/proc/net/tcp", "r", encoding="utf-8") as f:
    next(f)
    for line in f:
        local_address = line.split()[1]
        host_hex, port_hex = local_address.split(":")
        if int(port_hex, 16) != port:
            continue
        bytes_rev = bytes.fromhex("".join(reversed([host_hex[i:i+2] for i in range(0, len(host_hex), 2)])))
        found.append(socket.inet_ntoa(bytes_rev))
if found:
    for ip in found:
        print(f"{ip}:{port}")
PY
)
fi
if [[ -n "${LISTEN_OUTPUT}" ]]; then
    echo "${LISTEN_OUTPUT}"
else
    echo "No existing listener on ${PORT}."
fi

echo "Stopping any running ZenML server..."
zenml server stop &>/dev/null || zenml down &>/dev/null || true
zenml logout >/dev/null 2>&1 || true

echo "Starting ZenML server on 0.0.0.0:${PORT}..."
if zenml server start --host "${ZENML_LOCAL_SERVER_HOST}" --port "${PORT}"; then
    echo "Started via 'zenml server start'."
else
    echo "'zenml server start' unavailable; trying local login workflows..."
    if ZENML_LOCAL_SERVER_HOST="${ZENML_LOCAL_SERVER_HOST}" zenml login --local --ip-address "${ZENML_LOCAL_SERVER_HOST}" --port "${PORT}" --restart; then
        echo "Started via 'zenml login --local --ip-address ...'."
    elif ZENML_LOCAL_SERVER_HOST="${ZENML_LOCAL_SERVER_HOST}" zenml login --local --port "${PORT}" --restart; then
        echo "Started via env override 'ZENML_LOCAL_SERVER_HOST'."
    else
        echo "Falling back to 'zenml up' for legacy CLI versions..."
        if ! ZENML_LOCAL_SERVER_HOST="${ZENML_LOCAL_SERVER_HOST}" zenml up --port "${PORT}" --ip-address "${ZENML_LOCAL_SERVER_HOST}"; then
            echo "Fallback start command failed; printing ZenML help for diagnostics."
            zenml --help
            exit 1
        fi
    fi
fi

sleep 3

echo "Confirming listener on ${PORT}..."
if command -v ss >/dev/null 2>&1; then
    LISTEN_OUTPUT=$(ss -lntp | grep -F ":${PORT}" || true)
elif command -v netstat >/dev/null 2>&1; then
    LISTEN_OUTPUT=$(netstat -tlnp 2>/dev/null | grep -F ":${PORT}" || true)
else
    LISTEN_OUTPUT=$(ZENML_PORT="${PORT}" python - <<PY || true
import os
import socket
port = int(os.environ.get("ZENML_PORT", "8237"))
found = []
with open("/proc/net/tcp", "r", encoding="utf-8") as f:
    next(f)
    for line in f:
        local_address = line.split()[1]
        host_hex, port_hex = local_address.split(":")
        if int(port_hex, 16) != port:
            continue
        bytes_rev = bytes.fromhex("".join(reversed([host_hex[i:i+2] for i in range(0, len(host_hex), 2)])))
        found.append(socket.inet_ntoa(bytes_rev))
if found:
    for ip in found:
        print(f"{ip}:{port}")
PY
)
fi
if [[ -n "${LISTEN_OUTPUT}" ]]; then
    echo "${LISTEN_OUTPUT}"
    if grep -Eq "0\.0\.0\.0:${PORT}|\\*:${PORT}" <<<"${LISTEN_OUTPUT}"; then
        echo "Listener bound to all interfaces."
    else
        echo "Listener not bound to 0.0.0.0; dumping logs."
        zenml server logs >/dev/null 2>&1 || zenml logs || true
        exit 1
    fi
else
    echo "ZenML server not bound to 0.0.0.0:${PORT}; dumping logs."
    zenml server logs >/dev/null 2>&1 || zenml logs || true
    exit 1
fi

echo "Probing HTTP endpoint..."
PROBE_OUTPUT=""
if command -v curl >/dev/null 2>&1; then
    if PROBE_OUTPUT=$(curl -fsS "http://127.0.0.1:${PORT}/"); then
        PROBE_OUTPUT=$(printf "%s\n" "${PROBE_OUTPUT}" | head -n 5)
    else
        PROBE_OUTPUT=""
    fi
elif command -v wget >/dev/null 2>&1; then
    if PROBE_OUTPUT=$(wget -qO- "http://127.0.0.1:${PORT}/"); then
        PROBE_OUTPUT=$(printf "%s\n" "${PROBE_OUTPUT}" | head -n 5)
    else
        PROBE_OUTPUT=""
    fi
else
    PROBE_OUTPUT=$(ZENML_PORT="${PORT}" python - <<PY || true
import os
import urllib.request
port = int(os.environ.get("ZENML_PORT", "8237"))
try:
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=5) as resp:
        data = resp.read().decode("utf-8", "replace")
except Exception as exc:
    raise SystemExit(str(exc))
print("\\n".join(data.splitlines()[:5]))
PY
)
fi

if [[ -z "${PROBE_OUTPUT}" ]]; then
    echo "HTTP probe failed; dumping ZenML server logs."
    zenml server logs >/dev/null 2>&1 || zenml logs || true
    exit 1
fi

printf "%s\n" "${PROBE_OUTPUT}"

echo "ZenML dashboard reachable at http://localhost:${PORT}"
