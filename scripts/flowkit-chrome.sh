#!/bin/sh
set -eu

UNIT="${FLOWKIT_CHROME_UNIT:-flowkit-chrome.service}"
BASE_URL="${FLOWKIT_BASE_URL:-http://127.0.0.1:8100}"

usage() {
  printf 'Usage: %s {start|stop|force-stop|status}\n' "$0" >&2
  exit 2
}

extension_connected() {
  curl -fsS "${BASE_URL}/health" |
    python3 -c 'import json,sys; raise SystemExit(0 if json.load(sys.stdin).get("extension_connected") is True else 1)'
}

processing_count() {
  curl -fsS "${BASE_URL}/api/requests?status=PROCESSING" |
    python3 -c 'import json,sys; data=json.load(sys.stdin); print(len(data) if isinstance(data, list) else 1)'
}

case "${1:-}" in
  start)
    sudo systemctl start "$UNIT"
    attempt=0
    while [ "$attempt" -lt 60 ]; do
      if extension_connected 2>/dev/null; then
        printf 'FlowKit Chrome is ready.\n'
        exit 0
      fi
      attempt=$((attempt + 1))
      sleep 1
    done
    printf 'Chrome started, but the extension did not become ready in 60 seconds.\n' >&2
    exit 1
    ;;
  stop)
    if ! count="$(processing_count)"; then
      printf 'Cannot verify active work; use force-stop only for incident recovery.\n' >&2
      exit 1
    fi
    if [ "$count" -ne 0 ]; then
      printf 'Refusing to stop: %s request(s) are PROCESSING.\n' "$count" >&2
      exit 1
    fi
    sudo systemctl stop "$UNIT"
    printf 'FlowKit Chrome stopped; the API agent and queue remain online.\n'
    ;;
  force-stop)
    sudo systemctl stop "$UNIT"
    printf 'FlowKit Chrome force-stopped. Check interrupted requests before retrying.\n'
    ;;
  status)
    systemctl --no-pager --full status "$UNIT" || true
    if extension_connected 2>/dev/null; then
      printf 'Extension: connected\n'
    else
      printf 'Extension: disconnected\n'
    fi
    ;;
  *)
    usage
    ;;
esac
