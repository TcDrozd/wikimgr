# Wiki Manager API

Canonical base path: `/api/v1`

## Auth

- Optional API key enforcement via `WIKIMGR_API_KEY`.
- If set, send `X-API-Key: <value>` on all non-health endpoints.

## Idempotency

Upsert supports both headers:
- `X-Idempotency-Key` (canonical)
- `x_idempotency_key` (legacy compatibility)

## Canonical Endpoints

### Health
- `GET /api/v1/health` -> `200 {"ok": true}`
- `GET /api/v1/ready` -> `200 {"ready": true}` or `503 {"ready": false, "reason": "..."}`

### Pages
- `POST /api/v1/pages/upsert`
- `GET /api/v1/pages?path=...`
- `GET /api/v1/pages/{id}`
- `DELETE /api/v1/pages?path=...`
- `DELETE /api/v1/pages/{id}`

Upsert example:

```http
POST /api/v1/pages/upsert
X-Idempotency-Key: demo-001
Content-Type: application/json
```

```json
{
  "path": "automation/services/wikimgr",
  "title": "Wiki Manager Service (wikimgr)",
  "content": "# Title\n\nBody here.",
  "description": "Short summary",
  "is_private": false,
  "tags": ["backend", "fastapi", "automation"]
}
```

```json
{ "id": 123, "path": "automation/services/wikimgr", "idempotency_key": "demo-001" }
```

### Bulk
- `POST /api/v1/pages/bulk-move`
- `POST /api/v1/pages/bulk-redirect`
- `POST /api/v1/pages/bulk-relink`
- `GET /api/v1/pages/inventory`

Bulk move example:

```json
{
  "moves": [
    { "from_path": "old/path", "to_path": "new/path", "merge": false }
  ],
  "dry_run": true
}
```

```json
{
  "dry_run": true,
  "applied": [{ "from": "old/path", "to": "new/path", "dry": true }],
  "skipped": [],
  "errors": []
}
```

## Error Model

Canonical endpoints return a consistent error shape:

```json
{
  "code": "upstream_error",
  "message": "Wiki.js GraphQL error: ...",
  "details": null
}
```

Mapped statuses:
- `400` bad request/path policy
- `401` auth failure
- `404` page not found
- `502` upstream GraphQL/processing failure
- `504` upstream network timeout

## Legacy Endpoints (Deprecated)

All legacy routes are still available and include:
- `Deprecation: true`
- `Link: </api/v1/...>; rel="successor-version"`

Legacy compatibility routes:
- `GET /healthz` -> successor `/api/v1/health`
- `GET /readyz` -> successor `/api/v1/ready`
- `POST /pages/upsert` -> successor `/api/v1/pages/upsert`
- `POST /pages/upload` -> successor `/api/v1/pages/upsert`
- `POST /pages/bulk_upload` -> successor `/api/v1/pages/upsert`
- `GET /wikimgr/get` -> successor `/api/v1/pages`
- `POST /wikimgr/delete` -> successor `/api/v1/pages`
- `GET /wikimgr/health` -> successor `/api/v1/health`
- `POST /wikimgr/pages/bulk-move` -> successor `/api/v1/pages/bulk-move`
- `POST /wikimgr/pages/bulk-redirect` -> successor `/api/v1/pages/bulk-redirect`
- `POST /wikimgr/pages/bulk-relink` -> successor `/api/v1/pages/bulk-relink`
- `GET /wikimgr/pages/inventory.json` -> successor `/api/v1/pages/inventory`
