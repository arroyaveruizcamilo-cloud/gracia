import os
import time
import logging
from collections import defaultdict
from fastapi import Request
from fastapi.responses import JSONResponse

logger = logging.getLogger("gracia.ratelimit")

LIMITS = {
    "/api/auth/login": (int(os.getenv("RATE_LIMIT_LOGIN", "10")), 60),
    "/api/auth/register": (int(os.getenv("RATE_LIMIT_REGISTER", "5")), 3600),
    "/api/auth/forgot-password": (int(os.getenv("RATE_LIMIT_FORGOT", "5")), 3600),
    "/api/auth/reset-password": (int(os.getenv("RATE_LIMIT_RESET", "10")), 3600),
    "/api/messages": (int(os.getenv("RATE_LIMIT_MESSAGES", "5")), 3600),
}

# Backend en memoria (fallback). No comparte estado entre instancias/workers:
# configurá REDIS_URL en producción para rate limiting real.
_hits: dict[str, list[float]] = defaultdict(list)

REDIS_URL = os.getenv("REDIS_URL", "")
_redis = None
_redis_ready = False


def _get_redis():
    """Devuelve el cliente Redis si REDIS_URL está configurado y es alcanzable."""
    global _redis, _redis_ready
    if _redis_ready or not REDIS_URL:
        return _redis
    try:
        import redis as _redis_lib
        _redis = _redis_lib.from_url(REDIS_URL, decode_responses=True)
        _redis.ping()
    except Exception as e:
        logger.warning(f"Redis no disponible, usando rate limit en memoria: {e}")
        _redis = None
    _redis_ready = True
    return _redis


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for", "")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _limit_memory(key: str, max_req: int, window: int) -> bool:
    now = time.time()
    _hits[key] = [t for t in _hits[key] if t > now - window]
    if len(_hits[key]) >= max_req:
        return True
    _hits[key].append(now)
    return False


def _limit_redis(key: str, max_req: int, window: int) -> bool:
    r = _get_redis()
    if r is None:
        return _limit_memory(key, max_req, window)
    try:
        pipe = r.pipeline()
        pipe.incr(key)
        pipe.expire(key, window)
        count, _ = pipe.execute()
        return count > max_req
    except Exception as e:
        logger.warning(f"Redis rate limit error, usando memoria: {e}")
        return _limit_memory(key, max_req, window)


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
            key = f"rl:{_client_ip(request)}|{request.url.path}"
            max_req, window = limit
            blocked = _limit_redis(key, max_req, window) if REDIS_URL else _limit_memory(key, max_req, window)
            if blocked:
                response = JSONResponse(
                    status_code=429,
                    content={"detail": "Demasiadas peticiones. Intentá de nuevo más tarde."},
                )
                await response(scope, receive, send)
                return

        await self.app(scope, receive, send)
