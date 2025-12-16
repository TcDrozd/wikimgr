#!/usr/bin/env python3
"""
Simple smoke test for wikimgr + Wiki.js integration.

Usage:
  API_URL (optional, default http://localhost:8080)
  WIKIMGR_API_KEY (optional) exported into env for authenticated endpoints

Run:
  python3 scripts/smoke_test.py
"""

import json
import os
import sys
import time
import uuid

import httpx

API_URL = os.getenv("API_URL", "http://localhost:8080").rstrip("/")
API_KEY = os.getenv("WIKIMGR_API_KEY", "")
TIMEOUT = 10


def headers_with_auth(idempotency_key=None):
    h = {"Content-Type": "application/json"}
    if API_KEY:
        h["X-API-Key"] = API_KEY
    if idempotency_key:
        h["X-Idempotency-Key"] = idempotency_key
    return h


def fail(msg):
    print("FAIL:", msg)
    sys.exit(2)


def ok(msg):
    print("OK:", msg)


def main():
    client = httpx.Client(timeout=TIMEOUT)
    # 1) readiness
    try:
        r = client.get(f"{API_URL}/readyz")
    except Exception as e:
        fail(f"readyz request failed: {e}")
    if r.status_code != 200:
        fail(f"readyz returned {r.status_code}: {r.text}")
    try:
        body = r.json()
        if not body.get("ready", False):
            fail(f"readyz says not ready: {body}")
    except Exception:
        fail(f"readyz response not JSON: {r.text}")
    ok("readyz OK")

    # create a unique path so repeated runs don't collide
    timestamp = int(time.time())
    path = f"smoke/test-{timestamp}-{uuid.uuid4().hex[:6]}"
    title = "Smoke Test Page"
    content_md = "# Smoke Test\n\nThis page was created by smoke_test.py"
    description = "smoke test"

    payload = {
        "path": path,
        "title": title,
        "content_md": content_md,
        "description": description,
        "is_private": False,
        "tags": ["smoke"],
    }
    idem = os.getenv("SMOKE_IDEMP_KEY") or f"smoke-{timestamp}-{uuid.uuid4().hex[:6]}"
    headers = headers_with_auth(idempotency_key=idem)

    # 2) upsert
    r = client.post(f"{API_URL}/pages/upsert", headers=headers, json=payload)
    if r.status_code != 200:
        fail(f"upsert failed: {r.status_code} {r.text}")
    try:
        data = r.json()
        page_id = data.get("id")
        returned_path = data.get("path")
        assert page_id and returned_path
    except Exception as e:
        fail(f"unexpected upsert response: {r.text} ({e})")
    ok(f"upsert OK (id={page_id}, path={returned_path})")

    # 3) get back the page via wikimgr internal GET
    r = client.get(f"{API_URL}/wikimgr/get", params={"path": path}, timeout=TIMEOUT)
    if r.status_code != 200:
        fail(f"wikimgr get failed: {r.status_code} {r.text}")
    try:
        got = r.json()
    except Exception:
        fail(f"get returned non-json: {r.text}")
    if content_md.strip().splitlines()[0] not in (got.get("content", "") or ""):
        # simple substring check
        fail(f"get returned content mismatch or empty. got: {got.get('content')!r}")
    ok("wikimgr/get content OK")

    # 4) inventory contains the page (request with include_content=true to be sure)
    r = client.get(
        f"{API_URL}/wikimgr/pages/inventory.json", params={"include_content": "true"}
    )
    if r.status_code != 200:
        fail(f"inventory fetch failed: {r.status_code} {r.text}")
    inv = r.json()
    pages = inv.get("pages", [])
    if not any(p.get("path", "").strip("/") == path.strip("/") for p in pages):
        fail(f"inventory did not include our page. inventory count={len(pages)}")
    ok("inventory includes page")

    # 5) delete cleanup (best-effort)
    del_payload = {"path": path, "soft": False}
    r = client.post(f"{API_URL}/wikimgr/delete", headers=headers, json=del_payload)
    if r.status_code not in (200, 404):
        print("WARN: delete returned unexpected status:", r.status_code, r.text)
    else:
        ok("delete (cleanup) OK")

    print("\nSMOKE TEST PASSED\n")
    client.close()


if __name__ == "__main__":
    main()
