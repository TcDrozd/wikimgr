# Wiki Manager API Reference (Payload Shapes)

This document reflects the current `wikimgr` service behavior.

## Common Headers
- `Content-Type: application/json` for JSON endpoints.
- `Content-Type: multipart/form-data` for upload endpoints.
- `X-API-Key: <value>` optional, only required when `WIKIMGR_API_KEY` is set.
- `X-Idempotency-Key: <value>` optional for `POST /pages/upsert` and `POST /pages/upload`.
- Legacy compatibility: `x_idempotency_key` (underscore) is also accepted.

## Canonical Path Preflight Rules
Used by `POST /content/preflight`:
- Strip surrounding whitespace.
- Ensure leading `/`.
- Collapse repeated `/`.
- Per segment: lowercase, spaces/underscores to `-`, replace non `[a-z0-9-]`, collapse repeated `-`, trim `-`.
- No trailing slash unless root (`/`).
- Allowed roots are loaded from `WIKIMGR_ALLOWED_ROOTS` (CSV), default:
  `homelab,projects,ai,personal,community,meta`.

## Health

### `GET /healthz`
Response:
```json
{ "ok": true }
```

### `GET /readyz`
Returns `200` only when `WIKIJS_BASE_URL` and `WIKIJS_API_TOKEN` are present in env, else `503`.

Ready response:
```json
{ "ready": true }
```

## Upsert Page (Create or Update)

### `POST /pages/upsert`
Create or update by path.

Headers:
- `Content-Type: application/json`
- `X-API-Key` (optional)
- `X-Idempotency-Key` (optional)

Body:
```json
{
  "path": "automation/services/wikimgr",
  "title": "Wiki Manager Service (wikimgr)",
  "content": "# Any markdown or large plain-text block",
  "description": "Short summary",
  "is_private": false,
  "tags": ["backend", "fastapi", "automation"]
}
```

Field rules:
- `path` string required. Normalized to lowercase and spaces become `-`.
- `title` string required.
- Exactly one of `content` or `content_md` is required. Both are accepted.
- `description` optional. Defaults to empty string when sent upstream.
- `is_private` optional. Defaults to `false`.
- `tags` optional. Defaults to `[]`.

Notes:
- Updates replace full page content/title/description/tags/privacy fields.
- Path policy enforces each segment length >= 3 after expansion (`ai -> artificial-intelligence`, etc.).

Response `200`:
```json
{
  "id": 123,
  "path": "automation/services/wikimgr",
  "idempotency_key": "manual-or-derived-key"
}
```

Errors:
- `400` path policy violation.
- `401` API key invalid/missing (when enabled).
- `502` upstream GraphQL error.
- `504` upstream network error.

## Upload Markdown

### `POST /pages/upload`
Upsert a page from a multipart `.md` upload.

Headers:
- `Content-Type: multipart/form-data`
- `X-API-Key` (optional)
- `X-Idempotency-Key` (optional, preferred over form `idempotency_key`)

Form fields:
- `file` required (`.md`, UTF-8 only)
- `path` required
- `title` required
- `description` optional (default `""`)
- `tags` optional (`["a","b"]` JSON list string or CSV `a,b`)
- `is_private` optional truthy string (`1,true,yes,on`)
- `idempotency_key` optional (used when header is absent)

Response `200`:
```json
{
  "ok": true,
  "idempotency_key": "derived-or-provided-key",
  "page": {
    "id": 123,
    "path": "automation/services/wikimgr",
    "idempotency_key": "derived-or-provided-key"
  }
}
```

Notes:
- If idempotency key is missing, service computes `sha256(path + "\\0" + title + "\\0" + content_md)`.
- `tags` parsing: valid JSON list is accepted; otherwise value is parsed as CSV.

Errors:
- `400` missing/invalid fields, invalid extension, invalid UTF-8, invalid tags JSON type.
- `401` API key invalid/missing (when enabled).
- `413` payload too large (enforced by runtime/proxy config).
- `422` malformed multipart/form-data shape (FastAPI request validation).

## Read / Delete Helpers

### `GET /wikimgr/get`
Fetch by `path` or `id`.

Query params:
- `path` string optional
- `id` int optional

Response `200`:
```json
{
  "id": 123,
  "path": "automation/services/wikimgr",
  "title": "Wiki Manager Service (wikimgr)",
  "description": "Short summary",
  "isPrivate": false,
  "createdAt": "2025-10-10T12:34:56.000Z",
  "updatedAt": "2025-10-12T07:12:03.000Z",
  "content": "# ...markdown..."
}
```

Errors:
- `404` page not found
- `500` upstream/other error

### `POST /wikimgr/delete`
Delete by `path` or `id` (best effort).

Body examples:
```json
{ "path": "automation/services/wikimgr" }
```
```json
{ "id": 123 }
```

Response `200`:
```json
{ "ok": true, "hard_deleted": true, "id": 123 }
```

Notes:
- If upstream role/version disallows delete, service may return `ok: false`.
- `soft` exists in the request model but is not currently acted on by handler logic.

## Content Discovery / Preflight

### `GET /content/tree`
Returns a deterministic path tree from Wiki.js page paths (`id`, `path`, `title` source data).

Response `200`:
```json
{
  "roots": {
    "ai": {
      "ollama": {}
    },
    "homelab": {
      "gpu-vm": {},
      "network": {}
    }
  },
  "stats": {
    "page_count": 3,
    "root_counts": {
      "ai": 1,
      "homelab": 2
    }
  }
}
```

Notes:
- Tree nodes are nested dictionaries keyed by path segment.
- Empty path segments are ignored.
- Segment ordering is alphabetical for deterministic output.

Errors:
- `502` failed to fetch/list pages from Wiki.js upstream.

### `POST /content/preflight`
Validate and normalize a raw path against canonical roots, then return suggestions.

Body:
```json
{ "path": "/Infra/Proxmox/GPU VM" }
```

Response `200`:
```json
{
  "input": "/Infra/Proxmox/GPU VM",
  "normalized": "/infra/proxmox/gpu-vm",
  "is_valid_root": false,
  "root": "infra",
  "allowed_roots": ["homelab", "projects", "ai", "personal", "community", "meta"],
  "suggestions": [
    "/homelab/proxmox/gpu-vm",
    "/homelab/proxmox/cluster"
  ],
  "warnings": [
    "Root 'infra' is not in allowed roots."
  ]
}
```

Notes:
- Does not create, move, or update pages. Preflight only.
- Suggestions include simple keyword-based root hints and existing-path near matches.

Errors:
- `422` invalid request shape.
- `502` failed to fetch/list pages from Wiki.js upstream.

## Bulk Operations

Base path: `/wikimgr/pages/*`

### `GET /wikimgr/health`
```json
{ "ok": true }
```

### `POST /wikimgr/pages/bulk-move`
Body:
```json
{
  "moves": [
    { "from_path": "old/path", "to_path": "new/path", "merge": false },
    { "from_path": "legacy/ai", "to_path": "new/overview", "merge": true }
  ],
  "dry_run": true
}
```

Response shape:
```json
{
  "dry_run": true,
  "applied": [{ "from": "old/path", "to": "new/path", "dry": true }],
  "skipped": [],
  "errors": []
}
```

### `POST /wikimgr/pages/bulk-redirect`
Body:
```json
{
  "redirects": [
    { "from_path": "old/x", "to_path": "new/x" }
  ]
}
```

Response:
```json
{
  "applied": [{ "from": "old/x", "to": "new/x" }],
  "errors": []
}
```

### `POST /wikimgr/pages/bulk-relink`
Body:
```json
{
  "mapping": {
    "old/path": "new/path",
    "legacy/thing": "modern/thing"
  },
  "scope": "all"
}
```

- `mapping` updates exact-path markdown links in `](/path)` format.
- `scope` can be `"all"`, `"touched"`, or a list of paths.

Response:
```json
{
  "updated": ["docs/new/path"],
  "errors": []
}
```

### `POST /pages/bulk_upload`
Bulk upsert from multipart markdown files.

Headers:
- `Content-Type: multipart/form-data`
- `X-API-Key` (optional)

Form fields:
- `files` required (one or more `.md` files, UTF-8)
- `base_path` required
- `description` optional shared description
- `tags` optional shared tags (JSON list string or CSV)
- `is_private` optional shared truthy string

Per-file behavior:
- `title` derived from filename stem.
- `path` derived as `base_path/title`.
- idempotency key derived as `sha256(path + "\\0" + title + "\\0" + content_md)`.

Response `200`:
```json
{
  "ok": true,
  "base_path": "imports/notes",
  "successes": [
    {
      "filename": "readme.md",
      "idempotency_key": "abc123...",
      "page": {
        "id": 123,
        "path": "imports/notes/readme",
        "idempotency_key": "abc123..."
      }
    }
  ],
  "failures": []
}
```

### `GET /wikimgr/pages/inventory.json?include_content=false`
Response:
```json
{
  "count": 42,
  "pages": [
    {
      "id": 123,
      "path": "automation/services/wikimgr",
      "title": "Wiki Manager Service (wikimgr)",
      "description": "Short summary",
      "isPrivate": false,
      "createdAt": "...",
      "updatedAt": "..."
    }
  ]
}
```

When `include_content=true`, each page object also includes `content`.

## Curl Example

```bash
curl -X POST http://<host>:8080/pages/upsert \
  -H "Content-Type: application/json" \
  -H "X-Idempotency-Key: demo-001" \
  -d '{
    "path": "automation/services/wikimgr",
    "title": "Wiki Manager Service (wikimgr)",
    "content": "# Title\\n\\nBody here.",
    "description": "Short summary",
    "is_private": false,
    "tags": ["backend","fastapi","automation"]
  }'
```

## Build The Payload In iOS Shortcuts

Use this action sequence:
1. `Ask for Input` (Path)
2. `Ask for Input` (Title)
3. `Ask for Input` (Content)
4. Optional `Ask for Input` (Description)
5. `Dictionary` action for payload
6. `Get Contents of URL` action (`POST`)

### Dictionary action (payload)
Create keys:
- `path` -> Path input
- `title` -> Title input
- `content` -> Content input
- `description` -> Description input (or empty text)
- `is_private` -> `false` (Boolean)
- `tags` -> `List` (e.g. `backend`, `fastapi`, `automation`) or empty list

Equivalent JSON:
```json
{
  "path": "automation/services/wikimgr",
  "title": "Wiki Manager Service (wikimgr)",
  "content": "# Markdown or plain text",
  "description": "Short summary",
  "is_private": false,
  "tags": ["backend", "fastapi", "automation"]
}
```

### Get Contents of URL action
Configure:
- URL: `http://<your-host>:8080/pages/upsert`
- Method: `POST`
- Request Body: `JSON`
- JSON: the Dictionary from above
- Headers:
  - `Content-Type` = `application/json`
  - `X-Idempotency-Key` = `shortcut-<timestamp-or-uuid>`
  - `X-API-Key` = `<key>` only if your server requires API key

### Optional follow-up actions
- `Get Dictionary Value` from response for `id`, `path`, `idempotency_key`.
- `Show Result` with formatted confirmation.
