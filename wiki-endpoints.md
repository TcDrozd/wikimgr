# Wiki Manager API Reference (Payload Shapes)

This document reflects the current `wikimgr` service behavior.

## Common Headers
- `Content-Type: application/json` for JSON endpoints.
- `X-API-Key: <value>` optional, only required when `WIKIMGR_API_KEY` is set.
- `X-Idempotency-Key: <value>` optional for `POST /pages/upsert`.
- Legacy compatibility: `x_idempotency_key` (underscore) is also accepted.

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
