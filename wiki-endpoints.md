# Wiki Manager Endpoint Examples

This file is a quick call-by-call companion to `docs/api.md`.
Canonical API: `/api/v1`

## Canonical (`/api/v1`)

### `GET /api/v1/health`
```bash
curl -sS "http://localhost:8080/api/v1/health"
```

### `GET /api/v1/ready`
```bash
curl -sS -i "http://localhost:8080/api/v1/ready"
```

### `POST /api/v1/pages/upsert`
```bash
curl -sS -X POST "http://localhost:8080/api/v1/pages/upsert" \
  -H "Content-Type: application/json" \
  -H "X-Idempotency-Key: demo-001" \
  -d '{
    "path": "automation/services/wikimgr",
    "title": "Wiki Manager Service (wikimgr)",
    "content": "# Title\\n\\nBody here.",
    "description": "Short summary",
    "is_private": false,
    "tags": ["backend", "fastapi", "automation"]
  }'
```

### `GET /api/v1/pages?path=...`
```bash
curl -sS "http://localhost:8080/api/v1/pages?path=automation/services/wikimgr"
```

### `GET /api/v1/pages/{id}`
```bash
curl -sS "http://localhost:8080/api/v1/pages/123"
```

### `DELETE /api/v1/pages?path=...`
```bash
curl -sS -X DELETE "http://localhost:8080/api/v1/pages?path=automation/services/wikimgr"
```

### `DELETE /api/v1/pages/{id}`
```bash
curl -sS -X DELETE "http://localhost:8080/api/v1/pages/123"
```

### `POST /api/v1/pages/bulk-move`
```bash
curl -sS -X POST "http://localhost:8080/api/v1/pages/bulk-move" \
  -H "Content-Type: application/json" \
  -d '{
    "moves": [
      {"from_path": "old/path", "to_path": "new/path", "merge": false}
    ],
    "dry_run": true
  }'
```

### `POST /api/v1/pages/bulk-redirect`
```bash
curl -sS -X POST "http://localhost:8080/api/v1/pages/bulk-redirect" \
  -H "Content-Type: application/json" \
  -d '{
    "redirects": [
      {"from_path": "old/path", "to_path": "new/path"}
    ]
  }'
```

### `POST /api/v1/pages/bulk-relink`
```bash
curl -sS -X POST "http://localhost:8080/api/v1/pages/bulk-relink" \
  -H "Content-Type: application/json" \
  -d '{
    "mapping": {"old/path": "new/path"},
    "scope": "all"
  }'
```

### `GET /api/v1/pages/inventory`
```bash
curl -sS "http://localhost:8080/api/v1/pages/inventory?include_content=false"
```

## Legacy Compatibility (Deprecated)

These still work and return deprecation headers.

### `GET /healthz`
```bash
curl -sS -i "http://localhost:8080/healthz"
```

### `GET /readyz`
```bash
curl -sS -i "http://localhost:8080/readyz"
```

### `POST /pages/upsert`
```bash
curl -sS -X POST "http://localhost:8080/pages/upsert" \
  -H "Content-Type: application/json" \
  -d '{"path":"automation/services/wikimgr","title":"Wiki Manager","content":"# body"}'
```

### `POST /pages/upload`
```bash
curl -sS -X POST "http://localhost:8080/pages/upload" \
  -F "path=automation/services/wikimgr" \
  -F "title=Wiki Manager" \
  -F "file=@README.md;type=text/markdown"
```

### `POST /pages/bulk_upload`
```bash
curl -sS -X POST "http://localhost:8080/pages/bulk_upload" \
  -F "base_path=automation/services/imports" \
  -F "files=@README.md;type=text/markdown"
```

### `GET /wikimgr/get`
```bash
curl -sS "http://localhost:8080/wikimgr/get?path=automation/services/wikimgr"
```

### `POST /wikimgr/delete`
```bash
curl -sS -X POST "http://localhost:8080/wikimgr/delete" \
  -H "Content-Type: application/json" \
  -d '{"path":"automation/services/wikimgr"}'
```

### `GET /wikimgr/health`
```bash
curl -sS -i "http://localhost:8080/wikimgr/health"
```

### `POST /wikimgr/pages/bulk-move`
```bash
curl -sS -X POST "http://localhost:8080/wikimgr/pages/bulk-move" \
  -H "Content-Type: application/json" \
  -d '{"moves":[{"from_path":"old/path","to_path":"new/path","merge":false}],"dry_run":true}'
```

### `POST /wikimgr/pages/bulk-redirect`
```bash
curl -sS -X POST "http://localhost:8080/wikimgr/pages/bulk-redirect" \
  -H "Content-Type: application/json" \
  -d '{"redirects":[{"from_path":"old/path","to_path":"new/path"}]}'
```

### `POST /wikimgr/pages/bulk-relink`
```bash
curl -sS -X POST "http://localhost:8080/wikimgr/pages/bulk-relink" \
  -H "Content-Type: application/json" \
  -d '{"mapping":{"old/path":"new/path"},"scope":"all"}'
```

### `GET /wikimgr/pages/inventory.json`
```bash
curl -sS "http://localhost:8080/wikimgr/pages/inventory.json?include_content=false"
```

## Additional Unversioned Endpoints

These are currently still exposed outside `/api/v1`.

### `GET /content/tree`
```bash
curl -sS "http://localhost:8080/content/tree"
```

### `POST /content/preflight`
```bash
curl -sS -X POST "http://localhost:8080/content/preflight" \
  -H "Content-Type: application/json" \
  -d '{"path":"/Infra/Proxmox/GPU VM"}'
```
