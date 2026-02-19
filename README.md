# Wiki Manager (wikimgr)

Automates creation/updates of Wiki.js pages via a FastAPI service. Includes path normalization, idempotency, tags, locale handling, and bulk operations for moving, redirecting, and relinking pages.

## Quick Start

```bash
# 1) Create venv & install
python -m venv .venv && source .venv/bin/activate
pip install -e .

# 2) Configure env
cp .env.example .env   # then fill in values
export $(cat .env | xargs) # or use `direnv`

# Optional: canonical roots used by /content/preflight
# WIKIMGR_ALLOWED_ROOTS=homelab,projects,ai,personal,community,meta

# 3) Run
make dev    # uvicorn app.main:app --reload --port 8080

# 4) Health checks
curl -s http://localhost:8080/api/v1/health
curl -s http://localhost:8080/api/v1/ready
```

## API

Canonical API is versioned under `/api/v1`.

- Full reference: `docs/api.md`
- Quick endpoint examples: `wiki-endpoints.md`

Canonical endpoints:
- `GET /api/v1/health`
- `GET /api/v1/ready`
- `POST /api/v1/pages/upsert`
- `GET /api/v1/pages?path=...`
- `GET /api/v1/pages/{id}`
- `DELETE /api/v1/pages?path=...`
- `DELETE /api/v1/pages/{id}`
- `POST /api/v1/pages/bulk-move`
- `POST /api/v1/pages/bulk-redirect`
- `POST /api/v1/pages/bulk-relink`
- `GET /api/v1/pages/inventory`

Compatibility endpoints (deprecated, still supported):
- `GET /healthz`
- `GET /readyz`
- `POST /pages/upsert`
- `POST /pages/upload`
- `POST /pages/bulk_upload`
- `GET /wikimgr/get`
- `POST /wikimgr/delete`
- `GET /wikimgr/health`
- `POST /wikimgr/pages/bulk-move`
- `POST /wikimgr/pages/bulk-redirect`
- `POST /wikimgr/pages/bulk-relink`
- `GET /wikimgr/pages/inventory.json`

Legacy responses include migration headers:
- `Deprecation: true`
- `Link: </api/v1/...>; rel="successor-version"`

Auth and idempotency:
- If `WIKIMGR_API_KEY` is set, all non-health endpoints require `X-API-Key`.
- Upsert accepts both `X-Idempotency-Key` and legacy `x_idempotency_key`.
- Path policy behavior is unchanged: normalized lowercase/hyphenated paths and segment minimum length after expansions (for example `ai` -> `artificial-intelligence`).

## CLI Helper Script – `scripts/upsert_page.sh`

A small wrapper so you don't need to hand-craft JSON or escape large text payloads.

### Usage

```bash
scripts/upsert_page.sh <path> <title> <text_file> [description] [tags_json] [idempotency_key]
```

**Arguments**
- `<path>` – wiki path; will be normalized/expanded (e.g. `AI/Tools/Ollama` → `artificial-intelligence/tools/ollama`).
- `<title>` – page title.
- `<text_file>` – path to any local text file to use as page content.
- `[description]` – optional short description (default: empty string).
- `[tags_json]` – optional JSON array of strings, e.g. `'["backend","fastapi"]'` (default: `[]`).
- `[idempotency_key]` – optional unique string to make retries safe (default: `cli-upsert-<timestamp>`).

**Environment**
- `API_URL` (default `http://localhost:8080`)
- `WIKIMGR_API_KEY` (optional; adds `X-API-Key` header if set)
- `WIKIJS_BASE_URL`, `WIKIJS_API_TOKEN`, `WIKIJS_LOCALE` should be set where the service runs (they are used by the FastAPI app, not the script).

### Examples

Create:
```bash
scripts/upsert_page.sh \
  automation/services/wikimgr \
  "Wiki Manager Service (wikimgr)" \
  wikimgr.md \
  "Service that upserts Wiki.js pages" \
  '["backend","fastapi","automation","wikijs","service"]' \
  upsert-wikimgr-001
```

Update (replace content):
```bash
scripts/upsert_page.sh \
  automation/services/wikimgr \
  "Wiki Manager Service (wikimgr)" \
  wikimgr_updated.md \
  "Service that upserts Wiki.js pages" \
  '["backend","fastapi","automation","wikijs","service"]' \
  upsert-wikimgr-002
```

> The script uses `jq -Rs` to JSON-escape file content automatically, so large text blocks are sent safely without manual escaping.

## Makefile Targets

```makefile
run:    ## Run server (0.0.0.0:8080)
	uvicorn app.main:app --host 0.0.0.0 --port 8080

dev:    ## Dev server with reload
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8080

test:   ## Run tests
	pytest

lint:   ## Lint code
	python -m pyflakes app || true

format: ## Format code
	python -m black .
```

## Building an Apple Shortcut (macOS/iOS)

Yes — super straightforward. Two common approaches:

### A) Run the helper script locally (macOS)
1. **Shortcuts** → new shortcut → add *Run Shell Script*.
2. *Shell*: `/bin/zsh` (or `/bin/bash`).
3. *Script*:
   ```bash
   PATH="$HOME/bin:/usr/local/bin:/opt/homebrew/bin:$PATH"
   cd "$HOME/Projects/homelab-remote/wikimgr"
   scripts/upsert_page.sh \
     "$(Ask for Text: Path)" \
     "$(Ask for Text: Title)" \
     "$(Choose from Menu: Pick Markdown File path or hardcode)" \
     "$(Ask for Text: Description)" \
     '$(Ask for Text: Tags JSON e.g. ["backend"])' \
     "$(Ask for Text: Idempotency Key)"
   ```
4. Optionally set environment (`API_URL`, `WIKIMGR_API_KEY`) at the top of the script or via Shortcuts input variables.

### B) Call the FastAPI directly (macOS/iOS)
1. **Get File** (text source) → **Get Contents of File** → variable `MD`.
2. **Text** action to build a JSON body with tokens:
   ```json
   {
     "path": "${Path}",
     "title": "${Title}",
     "content": "${MD}",
     "description": "${Description}",
     "is_private": false,
     "tags": ${TagsJSON}
   }
   ```
3. **Get Contents of URL** → POST `http://localhost:8080/api/v1/pages/upsert` (or your host) with headers:
   - `Content-Type: application/json`
   - `X-API-Key: ${WIKIMGR_API_KEY}` (if used)
   - `X-Idempotency-Key: ${Idem}`

> Tip: On iOS, prefer **Approach B** to avoid local shell execution; on macOS, **Approach A** is easiest if you keep the repo checked out.

## Troubleshooting
- **Path rejected / odd errors**: ensure each segment ≥ 3 chars. Client expands common short segments (e.g. `ai` → `artificial-intelligence`).
- **GraphQL errors about tags/description**: these are required by schema; service provides defaults (`[]` and empty string) unless you override.
- **401 from wikimgr**: set/clear `WIKIMGR_API_KEY` to match your request.
- **404 from Wiki.js endpoint**: ensure `/graphql` on the base URL responds and the Bearer token is valid.
- **Bulk operations fail**: check inventory endpoint first; ensure source pages exist. Use `dry_run=true` for safe testing.
- **Link relinking misses links**: regex targets `](/path)` format; custom link formats may not be updated.
