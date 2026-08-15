import os

ENVIRONMENT = os.getenv("ENVIRONMENT", "development")


class SecurityHeadersMiddleware:
    """Agrega cabeceras de seguridad HTTP a todas las respuestas."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.extend(self._headers())
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_wrapper)

    def _headers(self):
        h = [
            (b"X-Content-Type-Options", b"nosniff"),
            (b"X-Frame-Options", b"SAMEORIGIN"),
            (b"Referrer-Policy", b"strict-origin-when-cross-origin"),
            (b"Permissions-Policy",
             b"camera=(), microphone=(), geolocation=(), payment=(), usb=(), interest-cohort=()"),
            (b"Cross-Origin-Opener-Policy", b"same-origin"),
            (b"Cross-Origin-Resource-Policy", b"same-origin"),
        ]
        if ENVIRONMENT == "production":
            h.append((b"Strict-Transport-Security",
                      b"max-age=31536000; includeSubDomains; preload"))
        csp = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.socket.io https://www.googletagmanager.com "
            "https://www.google-analytics.com https://connect.facebook.net https://js.stripe.com; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdnjs.cloudflare.com; "
            "img-src 'self' data: https: http://localhost:*; "
            "font-src 'self' https://fonts.gstatic.com https://cdnjs.cloudflare.com data:; "
            "connect-src 'self' https://www.google-analytics.com https://www.googletagmanager.com "
            "https://graph.facebook.com https://api.mercadopago.com https://mercadopago.com "
            "https://js.stripe.com wss: ws:; "
            "frame-src https://www.mercadopago.com https://js.stripe.com; "
            "object-src 'none'; base-uri 'self'; form-action 'self'"
        )
        h.append((b"Content-Security-Policy", csp.encode()))
        return h
