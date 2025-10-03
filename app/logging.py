import json
import logging
import uuid
from starlette.requests import Request
from starlette.responses import Response

def setup_logging():
    logging.basicConfig(level=logging.INFO)

async def inject_request_id(request: Request, call_next):
    req_id = request.headers.get("X-Request-Id", str(uuid.uuid4()))
    # attach to logger via context
    logger = logging.getLogger("wikimgr")
    request.state.req_id = req_id
    response: Response = await call_next(request)
    response.headers["X-Request-Id"] = req_id
    # basic access log
    logger.info(json.dumps({
        "msg": "request",
        "req_id": req_id,
        "method": request.method,
        "path": request.url.path,
        "status": response.status_code,
    }))
    return response