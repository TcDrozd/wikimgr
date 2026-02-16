# wikimgr Catch-Up (repo audit)

## Executive Summary
- `wiki-endpoints.md` is **not fully correct** for current code.
- Core service is a FastAPI app with two Wiki.js integration paths:
  - async GraphQL client for upsert (`app/wikijs_client.py`)
  - sync GraphQL helpers for get/delete/inventory (`app/wikijs_api.py`)
- Bulk operations call internal HTTP endpoints rather than in-process functions (`app/bulk_ops.py`).
- Several high-impact drift/bugs exist in auth header behavior, docs, tests, and one likely runtime bug in bulk relink inventory parsing.

## Is `wiki-endpoints.md` Correct?
Verdict: **Partially**. Some sections are accurate, but there are important mismatches and one markdown formatting bug.

### Confirmed correct points
- `GET /healthz` -> `{ "ok": true }` (`app/main.py`).
- `GET /readyz` checks only env presence and returns `200/503` accordingly (`app/main.py`).
- `POST /pages/upsert` returns `{id, path, idempotency_key}` (`app/main.py`).
- Path normalization/policy statements are directionally correct (`app/wikijs_client.py`).
- Bulk move/redirect/relink and inventory endpoints exist at documented routes (`app/bulk_ops.py`).

### Mismatches to fix in `wiki-endpoints.md`
1. Upsert payload field requirements are inaccurate.
- Doc says `content_md` is required and `is_private`, `tags`, `description` are required.
- Actual model accepts **either** `content` or `content_md`; `description` optional; `is_private` defaults false; `tags` is optional in model usage and defaults to `[]` at outbound GraphQL.
- Source: `app/models.py`, `app/wikijs_client.py`.

2. Idempotency header name is misleading in practice.
- Code reads `x_idempotency_key: Header(..., convert_underscores=False)` in `app/main.py`.
- In FastAPI this expects header name literally `x_idempotency_key`, not standard `X-Idempotency-Key` when `convert_underscores=False` is set.
- Doc states `X-Idempotency-Key` and implies it is echoed; currently likely not recognized unless client sends underscore variant.

3. `/wikimgr/delete` request body docs include `soft`, but endpoint ignores it.
- Model has `soft: bool = True` (`app/models.py`), but handler always calls hard delete attempt and returns result; no soft-delete branch in `app/main.py`.

4. `/wikimgr/pages/inventory.json` response shape in relink flow mismatch.
- Endpoint returns `{count, pages:[...]}` (`app/bulk_ops.py` inventory_json).
- `bulk_relink` currently does `pages = r.json()` then iterates `for p in pages:` expecting a list; this can break (string key iteration) and likely throws runtime errors.
- Doc describes inventory shape correctly; implementation consuming it is inconsistent.

5. `wiki-endpoints.md` contains markdown fence bug.
- File starts with `````markdown` on line 1 and never closes it.
- Source: `wiki-endpoints.md:1` and EOF.

6. Uploader section appears out-of-repo.
- `wiki-endpoints.md` documents a Flask uploader `/upload`, but no uploader service code exists in this repo.
- Keep if intentionally documenting companion service, but it should be labeled external and versioned separately.

## Core Components and How They Connect

### 1) API entrypoint
- File: `app/main.py`
- Responsibilities:
  - initialize FastAPI app
  - middleware for request ID/logging
  - include bulk router
  - expose `healthz`, `readyz`, `pages/upsert`, `wikimgr/get`, `wikimgr/delete`
- Dependencies:
  - `require_api_key` from `app/deps.py`
  - `WikiJSClient` for upsert
  - `wikijs_api` functions for get/delete

### 2) Data models
- File: `app/models.py`
- `PagePayload` supports backward compatibility (`content` + `content_md`) and requires one of them.
- `UpsertResult` is response contract for upsert.
- `DeleteReq` includes `soft`, but current handler does not use it.

### 3) Async Wiki.js write client
- File: `app/wikijs_client.py`
- Responsibilities:
  - normalize/enforce path policy (`normalize_path`, `enforce_path_policy`)
  - GraphQL transport with retry/backoff (`_gql`)
  - create/update/upsert by path
  - derive idempotency key
- Notes:
  - `upsert_page` checks existence by path+locale, then update or create.
  - tags/description defaults are injected before GraphQL calls.

### 4) Sync Wiki.js read/delete helpers
- File: `app/wikijs_api.py`
- Responsibilities:
  - path/id resolution, cached index refresh
  - fetch single page (with `content` then `contentRaw` fallback)
  - delete by id (best-effort false on errors)
- Notes:
  - Uses module-level env snapshot (`WIKIJS_BASE_URL`, token) at import time.

### 5) Bulk operations router
- File: `app/bulk_ops.py`
- Endpoints:
  - `/wikimgr/pages/bulk-move`
  - `/wikimgr/pages/bulk-redirect`
  - `/wikimgr/pages/bulk-relink`
  - `/wikimgr/pages/inventory.json`
- Design:
  - Performs internal HTTP calls to this same service (`/pages/upsert`, `/wikimgr/get`, `/wikimgr/delete`) via configurable URLs.
  - Link rewriting targets markdown links in `](/path)` format only.

### 6) Auth and logging
- Files: `app/deps.py`, `app/log_utils.py`
- `X-API-Key` auth is optional and enabled only if `WIKIMGR_API_KEY` is set.
- Request middleware injects/echoes `X-Request-Id` and logs method/path/status.

### 7) Scripts and tests
- Scripts: `scripts/upsert_page.sh`, `scripts/smoke_test.py`
- Tests: `tests/test_pages.py` (currently inconsistent import path; see issues)

## Glaring Issues / Bugs / Risks (prioritized)

### High
1. **Potentially broken idempotency header ingestion**
- `convert_underscores=False` likely prevents standard `X-Idempotency-Key` from binding in `app/main.py`.
- Impact: callers think they set key; server silently derives one.

2. **`bulk_relink` likely broken against current inventory response**
- Expects inventory JSON as list, but endpoint returns object with `pages` key.
- Impact: relink may fail or no-op unpredictably.
- Source: `app/bulk_ops.py` in `bulk_relink` + `inventory_json`.

3. **Internal bulk auth header mismatch**
- Bulk ops send `Authorization: Bearer ...` via `WKMGR_BEARER`.
- Main protected endpoint expects `X-API-Key` (`app/deps.py`).
- Impact: if API key is enabled, internal bulk calls can fail with 401 unless endpoint protection is bypassed or separately configured.

### Medium
4. **Tests appear stale/unrunnable as written**
- Import path in tests is `from wikimgr.app.main import app`, but module is `app.main`; confirmed `ModuleNotFoundError` for `wikimgr.app.main`.
- `pytest` is not in installed env/requirements in this workspace snapshot, though Makefile test target expects it.
- Impact: weak regression safety.

5. **Delete API contract drift (`soft` not honored)**
- Docs/JSON examples include soft delete concept, but implementation does hard-delete attempt only.
- Impact: client expectations mismatch.

6. **`wiki-endpoints.md` is partially stale and malformed markdown**
- Required/optional fields, headers, and uploader context are inconsistent.
- Unclosed top-level code fence breaks rendering.

### Low
7. **Mixed sync/async Wiki.js clients and env loading styles**
- `wikijs_client.py` resolves env at call time; `wikijs_api.py` captures some env at import.
- Not immediately broken, but raises consistency/maintainability risk.

8. **Bulk ops call local service over HTTP rather than in-process functions**
- Simpler decoupling, but adds network overhead and auth/config coupling complexity.

## What You May Be Overlooking
- There is an in-progress drift between docs (`README.md`, `wiki-endpoints.md`) and runtime contracts.
- Some files are already modified/untracked in git status, including `wiki-endpoints.md` and `ARCHITECTURE.md`; plan work should account for existing WIP state.
- If you enable API key auth in production, bulk ops likely need explicit alignment (`X-API-Key` propagation or alternate dependency strategy).
- Upsert currently has replace semantics for full page content; there is no append/merge behavior.
- Readiness endpoint is config-only, not live dependency health.

## Suggested Plan Inputs
1. First, decide source of truth for endpoint contracts (`README.md` vs `wiki-endpoints.md` vs OpenAPI schema).
2. Fix contract/runtime mismatches that can break clients (idempotency header, bulk relink parsing, bulk auth propagation).
3. Repair test harness/imports and add tests for bulk-relink + header handling.
4. Then refresh docs from code and optionally generate an API contract artifact.
