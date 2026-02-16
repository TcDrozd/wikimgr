# Architecture Map

## Overview
`wikimgr` is a FastAPI service that manages Wiki.js pages via GraphQL.

Primary responsibilities:
- upsert a single page by path (`create` or `update`)
- fetch/delete single pages
- bulk move, redirect, and relink operations
- provide page inventory for bulk workflows

## High-Level Component Map
```text
Clients (curl, scripts, Shortcuts)
        |
        v
FastAPI App (`app/main.py`)
  - health/readiness
  - single-page routes
  - middleware (request IDs + logs)
  - API key dependency
  - includes bulk router
        |
        +--> WikiJSClient (`app/wikijs_client.py`) [async GraphQL]
        |      - normalize/enforce path
        |      - find page by path
        |      - create/update/upsert
        |
        +--> Wiki.js API helpers (`app/wikijs_api.py`) [sync GraphQL]
        |      - resolve path->id
        |      - get single page
        |      - delete by id
        |      - refresh full index
        |
        +--> Bulk Ops Router (`app/bulk_ops.py`)
               - bulk-move / bulk-redirect / bulk-relink
               - inventory endpoint
               - calls internal HTTP endpoints (`/pages/upsert`, `/wikimgr/get`, `/wikimgr/delete`)
```

## Module Responsibilities

### `app/main.py`
- App bootstrap (`FastAPI(title="Wiki Manager")`)
- Loads `.env` via `python-dotenv`
- Registers middleware from `app/log_utils.py`
- Registers bulk router from `app/bulk_ops.py`
- Exposes routes:
  - `GET /healthz`
  - `GET /readyz`
  - `POST /pages/upsert`
  - `GET /wikimgr/get`
  - `POST /wikimgr/delete`

### `app/models.py`
Pydantic models:
- `PagePayload`
  - accepts `content` (preferred) or legacy `content_md`
- `UpsertResult`
- `DeleteReq`

### `app/wikijs_client.py`
Async Wiki.js GraphQL client used by upsert route:
- `normalize_path(raw)`
- `enforce_path_policy(path)`
- `WikiJSClient.from_env()`
- `get_page_by_path(path, locale)`
- `create_page(payload)`
- `update_page(page_id, payload)`
- `upsert_page(payload, idem_key)`
- `derive_idempotency_key(payload)`

### `app/wikijs_api.py`
Sync helpers used by get/delete/inventory:
- GraphQL query/mutation constants
- `_post(query, variables)`
- `_PATH_ID_CACHE` and `refresh_index()`
- `resolve_id(path|id)`
- `get_single(id)`
- `delete_by_id(id)`

### `app/bulk_ops.py`
Bulk endpoints and supporting utilities:
- internal HTTP helper calls to this same service
- markdown link rewriting (`rewrite_links`)
- moved-page stub content generation (`moved_stub`)
- routes:
  - `GET /wikimgr/health`
  - `POST /wikimgr/pages/bulk-move`
  - `POST /wikimgr/pages/bulk-redirect`
  - `POST /wikimgr/pages/bulk-relink`
  - `GET /wikimgr/pages/inventory.json`

### `app/deps.py`
- optional API key guard: `require_api_key`
- `X-API-Key` enforced only when `WIKIMGR_API_KEY` is set

### `app/log_utils.py`
- basic logging setup
- request ID middleware:
  - accepts incoming `X-Request-Id` or generates one
  - returns `X-Request-Id` response header
  - logs method/path/status

## Request Flow Maps

### 1) Single Upsert (`POST /pages/upsert`)
```text
Client
  -> app.main.upsert_page
    -> deps.require_api_key
    -> derive_idempotency_key (if header missing)
    -> WikiJSClient.from_env
    -> WikiJSClient.upsert_page
       -> normalize_path + enforce_path_policy
       -> get_page_by_path(singleByPath)
       -> update_page OR create_page
    -> UpsertResult
```

### 2) Single Get (`GET /wikimgr/get`)
```text
Client
  -> app.main.wikimgr_get
    -> wikijs_api.resolve_id(path|id)
    -> wikijs_api.get_single(id)
    -> page JSON
```

### 3) Single Delete (`POST /wikimgr/delete`)
```text
Client
  -> app.main.wikimgr_delete
    -> wikijs_api.resolve_id(path|id)
    -> wikijs_api.delete_by_id(id)
    -> {ok, hard_deleted, id}
```

### 4) Bulk Move (`POST /wikimgr/pages/bulk-move`)
```text
Client
  -> bulk_ops.bulk_move
    -> get_page(src) via internal GET /wikimgr/get
    -> upsert_page(dst) via internal POST /pages/upsert
    -> delete old OR upsert moved stub at src
```

### 5) Bulk Relink (`POST /wikimgr/pages/bulk-relink`)
```text
Client
  -> bulk_ops.bulk_relink
    -> fetch inventory
    -> for each page in scope:
       -> get current content
       -> rewrite markdown links with mapping
       -> upsert only if changed
```

## Environment and Configuration

Core Wiki.js connectivity:
- `WIKIJS_BASE_URL`
- `WIKIJS_API_TOKEN`
- `WIKIJS_LOCALE` (default `en`)

Service auth:
- `WIKIMGR_API_KEY` (optional)

Bulk/internal endpoint wiring:
- `WKMGR_BASE_URL` (default `http://127.0.0.1:8080`)
- `WKMGR_UPSERT_URL`
- `WKMGR_GET_URL`
- `WKMGR_DELETE_URL`
- `WKMGR_BEARER` (optional)
- `WKMGR_INVENTORY_JSON` (optional)

## Supporting Assets
- `scripts/upsert_page.sh`: shell helper to build JSON payload from any text file and call `/pages/upsert`
- `scripts/smoke_test.py`: end-to-end API smoke test
- `tests/test_pages.py`: lightweight FastAPI route tests (with monkeypatching)

## Known Architectural Notes
- Two integration styles coexist for Wiki.js access:
  - async client (`wikijs_client.py`) for upsert
  - sync helpers (`wikijs_api.py`) for get/delete/inventory
- Bulk operations use HTTP calls to internal endpoints rather than direct in-process function calls.
- Readiness check validates env presence, not live GraphQL connectivity.
