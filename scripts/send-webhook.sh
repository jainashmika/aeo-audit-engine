#!/usr/bin/env bash
# Simulate a banking portal notifying the engine that a product page changed.
# Usage: scripts/send-webhook.sh [institution] [url] [entity]
set -euo pipefail
SECRET="${AEO_WEBHOOK_SECRET:-change-me}"
INST="${1:-meridian}"
URL="${2:-http://nlp-worker:8000/demo-sites/meridian/etf/nifty-dividend-etf.html}"
ENTITY="${3:-meridian-nifty-dividend-etf}"
BODY="{\"institution\":\"$INST\",\"url\":\"$URL\",\"entity\":\"$ENTITY\",\"namespace\":\"Retail\"}"
SIG="sha256=$(printf '%s' "$BODY" | openssl dgst -sha256 -hmac "$SECRET" -r | cut -d' ' -f1)"
curl -sS -X POST http://localhost:8080/api/webhooks/portal-update \
  -H "Content-Type: application/json" -H "X-AEO-Signature: $SIG" -d "$BODY"
echo
