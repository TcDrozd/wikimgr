# wikimgr Catch-Up (Historical)

This file is retained as historical context from a prior audit and is no longer a source of truth.

Current authoritative API and architecture references:
- `docs/api.md` for canonical and legacy endpoint contracts
- `README.md` for project-level usage and migration notes

Notes:
- Bulk and single-page operations now run in-process through shared service modules.
- The old split-service/self-callback `app/bulk_ops.py` design has been removed.
