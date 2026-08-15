import os
import time
from collections import defaultdict
from fastapi import Request
from fastapi.responses import JSONResponse

LIMITS = {
    "/api/auth/login": (int(os.getenv("RATE_LIMIT_LOGIN", "10")), 60),
    "/api/auth/register": (int(os.getenv("RATE_LIMIT_REGISTER", "5")), 3600),
    "/api/auth/forgot-password": (int(os.getenv("RATE_LIMIT_FORGOT", "5")), 3600),
    "/api/auth/reset-password": (int(os.getenv("RATE_LIMIT_RESET", "10")), 3600),
    "/api/messages": (int(os.getenv("RATE_LIMIT_MESSAGES", "5")), 3600),
}

_hits: dict[str, list[float]] = defaultdict(list)


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for", "")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class RateLimitMiddleware:
    """Limita peticiones por IP en endpoints sensibles (auth, contacto)."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive)
        limit = None
        for prefix, (max_req, window) in LIMITS.items():
            if request.url.path == prefix or request.url.path.startswith(prefix + "/"):
                limit = (max_req, window)
                break

        if limit is not None and request.method == "POST":
            key = f"{_client_ip(request)}|{request.url.path}"
            now = time.time()
            max_req, window = limit
            _hits[key] = [t for t in _hits[key] if t > now - window]
            if len(_hits[key]) >= max_req:
                response = JSONResponse(
                    status_code=429,
                    content={"detail": "Demasiadas peticiones. Intentá de nuevo más tarde."},
                )
                await response(scope, receive, send)
                return
            _hits[key].append(now)

        await self.app(scope, receive, send)
