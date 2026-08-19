import os
import traceback
import logging
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette import status

logger = logging.getLogger("gracia")


async def global_error_handler(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception as e:
        logger.error(f"Unhandled error on {request.method} {request.url.path}: {e}\n{traceback.format_exc()}")
        # Send to Sentry before returning a clean response
        if os.getenv("SENTRY_DSN"):
            try:
                import sentry_sdk
                sentry_sdk.capture_exception(e)
            except Exception:
                pass
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"ok": False, "error": "Error interno del servidor"},
        )
