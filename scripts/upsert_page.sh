#!/usr/bin/env bash
# Ensure common locations are on PATH (Shortcuts has a very limited PATH)
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"

set -euo pipefail

usage() {
  cat <<EOF
Usage: $0 <path-slug> <title> <markdown-file> [description] [tags-json]
EOF
  exit 1
}

if [[ $# -lt 3 ]]; then
  usage
fi

PATH_SLUG="$1"
TITLE="$2"
MD_FILE="$3"
DESC="${4:-}"
TAGS_JSON="${5:-[]}"

if ! command -v curl >/dev/null 2>&1; then
  echo "curl is required"
  exit 1
fi

make_payload() {
  local path_slug="$1"; shift
  local title="$1"; shift
  local md_file="$1"; shift
  local desc="$1"; shift
  local tags_json="$1"; shift

  if command -v jq >/dev/null 2>&1; then
    jq -Rs \
      --arg path "$path_slug" \
      --arg title "$title" \
      --arg desc "$desc" \
      --argjson tags "$tags_json" '
      {
        path: $path,
        title: $title,
        content_md: .,
        description: $desc,
        is_private: false,
        tags: $tags
      }
    ' "$md_file" > /tmp/wikimgr_payload.json
  else
    /usr/bin/python3 - "$path_slug" "$title" "$md_file" "$desc" "$tags_json" <<'PY'
import json, sys
path, title, md_file, desc, tags_json = sys.argv[1:]
try:
    tags = json.loads(tags_json)
    if not isinstance(tags, list):
        raise ValueError
except Exception:
    tags = []
with open(md_file, 'r', encoding='utf-8') as f:
    content = f.read()
obj = {
    "path": path,
    "title": title,
    "content_md": content,
    "description": desc,
    "is_private": False,
    "tags": tags,
}
with open('/tmp/wikimgr_payload.json', 'w', encoding='utf-8') as out:
    json.dump(obj, out)
PY
  fi
}

API_URL="${API_URL:-http://localhost:8080}"
API_KEY_HEADER=""
if [[ -n "${WIKIMGR_API_KEY:-}" ]]; then
  API_KEY_HEADER='-H "X-API-Key: '"${WIKIMGR_API_KEY}"'"'
fi

make_payload "$PATH_SLUG" "$TITLE" "$MD_FILE" "$DESC" "$TAGS_JSON"

IDEMP=$(uuidgen)

curl -sS -X POST "${API_URL}/pages/upsert" \
  -H "Content-Type: application/json" \
  -H "X-Idempotency-Key: ${IDEMP}" \
  ${API_KEY_HEADER} \
  --data @/tmp/wikimgr_payload.json