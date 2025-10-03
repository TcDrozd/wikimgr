#!/usr/bin/env bash
set -euo pipefail

API_URL="${API_URL:-http://localhost:8080}"
API_KEY_HEADER=()
[[ -n "${WIKIMGR_API_KEY:-}" ]] && API_KEY_HEADER=(-H "X-API-Key: ${WIKIMGR_API_KEY}")

if [[ $# -lt 3 ]]; then
  echo "Usage: $0 <path> <title> <markdown_file> [description] [tags_json] [idempotency_key]" >&2
  exit 1
fi

PATH_SLUG="$1"
TITLE="$2"
MD_FILE="$3"
DESC="${4:-}"
TAGS_JSON="${5:-[]}"
IDEMP="${6:-cli-upsert-$(date +%s)}"

jq -Rs \
  --arg path "$PATH_SLUG" \
  --arg title "$TITLE" \
  --arg desc "$DESC" \
  --argjson tags "$TAGS_JSON" '
  {
    path: $path,
    title: $title,
    content_md: .,
    description: $desc,
    is_private: false,
    tags: $tags
  }' "$MD_FILE" > /tmp/wikimgr_payload.json

curl -sS -X POST "${API_URL}/pages/upsert" \
  -H "Content-Type: application/json" \
  -H "X-Idempotency-Key: ${IDEMP}" \
  "${API_KEY_HEADER[@]}" \
  --data @/tmp/wikimgr_payload.json
