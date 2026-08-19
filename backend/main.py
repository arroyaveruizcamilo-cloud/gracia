import sys
import os
import logging
from pathlib import Path
from contextlib import asynccontextmanager

sys.path.append(str(Path(__file__).resolve().parent))

try:
    import sentry_sdk
except ImportError:
    sentry_sdk = None
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, PlainTextResponse, HTMLResponse
from database import engine, Base, SessionLocal
from models import User, UserRole, Product
from auth import hash_password, verify_password
from middleware.error_handler import global_error_handler
import json
import socketio

SENTRY_DSN = os.getenv("SENTRY_DSN", "")
if SENTRY_DSN and sentry_sdk:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        environment=os.getenv("ENVIRONMENT", "development"),
        traces_sample_rate=0.1,
    )

from routers import (
    auth, products, orders, analytics, messages, users, coupons,
    faqs, payments, wompi, upload, chat, admin, banners, reviews,
)

ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("gracia")

# ─── Orígenes permitidos (CORS) ─────────────────────────────
allowed_origins_str = os.getenv("CORS_ORIGINS", "")
if ENVIRONMENT == "production":
    # En producción NO se permite wildcard con credenciales.
    # Si no se configura CORS_ORIGINS, se asume same-origin.
    if not allowed_origins_str or allowed_origins_str == "*":
        allowed_origins = []
    else:
        allowed_origins = [o.strip() for o in allowed_origins_str.split(",") if o.strip()]
else:
    allowed_origins = ["*"]

sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins=allowed_origins,
)
fastapi_app = FastAPI(title="Gracia Clothing API", version="2.0.0")
app = socketio.ASGIApp(sio, other_asgi_app=fastapi_app)

fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if ENVIRONMENT == "production":
    # TrustedHost necesita hostnames (sin esquema), no URLs.
    # Se incluye localhost para el HEALTHCHECK del Dockerfile y *.onrender.com
    # como valor seguro por defecto para los servicios de Render.
    hosts = ["localhost", "127.0.0.1"]
    for o in allowed_origins:
        host = o.split("://")[-1].rstrip("/").split("/")[0]
        if host and host not in hosts:
            hosts.append(host)
    extra_hosts = [h.strip() for h in os.getenv("ALLOWED_HOSTS", "").split(",") if h.strip()]
    hosts.extend(h for h in extra_hosts if h not in hosts)
    if "*.onrender.com" not in hosts:
        hosts.append("*.onrender.com")
    fastapi_app.add_middleware(TrustedHostMiddleware, allowed_hosts=hosts)

# Seguridad: cabeceras HTTP y rate limiting
from middleware.security_headers import SecurityHeadersMiddleware
from middleware.rate_limit import RateLimitMiddleware
fastapi_app.add_middleware(RateLimitMiddleware)
fastapi_app.add_middleware(SecurityHeadersMiddleware)

# Global error handler (no stack traces leaked in production)
fastapi_app.middleware("http")(global_error_handler)

# Serve uploaded files
uploads_dir = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(uploads_dir, exist_ok=True)
fastapi_app.mount("/uploads", StaticFiles(directory=uploads_dir), name="uploads")

ROOT_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = ROOT_DIR / "frontend"

# Serve the store as the main page
@fastapi_app.get("/")
def serve_index():
    return FileResponse(FRONTEND_DIR / "index.html")

fastapi_app.mount("/frontend", StaticFiles(directory=str(FRONTEND_DIR)), name="frontend")


@fastapi_app.get("/admin")
def serve_admin():
    return FileResponse(FRONTEND_DIR / "admin" / "index.html")


@fastapi_app.get("/reset-password")
def serve_reset_password():
    return FileResponse(FRONTEND_DIR / "index.html")


@fastapi_app.get("/legal/privacidad")
def serve_privacidad():
    return FileResponse(FRONTEND_DIR / "legal" / "privacidad.html")


@fastapi_app.get("/legal/terminos")
def serve_terminos():
    return FileResponse(FRONTEND_DIR / "legal" / "terminos.html")


SITE_URL = os.getenv("FRONTEND_URL", "https://graciaclothing.com").rstrip("/")


def serve_html_with_meta(html: str, title: str, description: str, image: str,
                         url: str, product_json: dict | None = None) -> HTMLResponse:
    from html import escape as _escape
    title = _escape(title)
    description = _escape(description)
    image = _escape(image)
    url = _escape(url)
    tags = f"""
  <title>{title}</title>
  <meta name="description" content="{description}">
  <link rel="canonical" href="{url}">
  <meta property="og:site_name" content="Gracia Clothing">
  <meta property="og:title" content="{title}">
  <meta property="og:description" content="{description}">
  <meta property="og:type" content="product">
  <meta property="og:url" content="{url}">
  <meta property="og:image" content="{image}">
  <meta property="og:locale" content="es_CO">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{title}">
  <meta name="twitter:description" content="{description}">
  <meta name="twitter:image" content="{image}">
"""
    if product_json:
        tags += f'<script type="application/ld+json">{json.dumps(product_json, ensure_ascii=False)}</script>\n'

    html = html.replace("</head>", tags + "</head>")
    return HTMLResponse(html)


@fastapi_app.get("/producto/{slug}")
def serve_product(slug: str):
    db = SessionLocal()
    try:
        p = db.query(Product).filter(
            Product.status == "active", Product.slug == slug
        ).first()
        if not p:
            p = db.query(Product).filter(Product.status == "active").all()
            p = next((x for x in p if (x.slug or "").lower() == slug.lower() or
                      x.name.lower().replace(" ", "-") == slug.lower().replace(" ", "-")), None)
        if not p:
            return FileResponse(FRONTEND_DIR / "index.html")

        image = p.image or "https://graciaclothing.com/frontend/assets/logo.svg"
        url = f"{SITE_URL}/producto/{slug}"
        product_json = {
            "@context": "https://schema.org",
            "@type": "Product",
            "name": p.name,
            "description": (p.description or "")[:300],
            "image": image,
            "url": url,
            "brand": {"@type": "Brand", "name": "Gracia Clothing"},
            "offers": {
                "@type": "Offer",
                "price": p.price,
                "priceCurrency": "COP",
                "availability": "https://schema.org/InStock" if p.stock > 0 else "https://schema.org/OutOfStock",
                "url": url,
            },
        }
        return serve_html_with_meta(
            (FRONTEND_DIR / "index.html").read_text(encoding="utf-8"),
            title=f"{p.name} — Gracia Clothing",
            description=(p.description or "")[:160],
            image=image,
            url=url,
            product_json=product_json,
        )
    finally:
        db.close()


@fastapi_app.get("/robots.txt")
def robots():
    return PlainTextResponse(f"""User-agent: *
Allow: /
Sitemap: {SITE_URL}/sitemap.xml
""")


@fastapi_app.get("/sitemap.xml")
def sitemap():
    from xml.sax.saxutils import escape
    db = SessionLocal()
    try:
        products = db.query(Product).filter(Product.status == "active").all()
        urls = [f"<url><loc>{SITE_URL}/</loc><priority>1.0</priority></url>"]
        urls.append(f"<url><loc>{SITE_URL}/admin</loc><priority>0.3</priority></url>")
        for p in products:
            slug = escape((p.slug or p.name.lower().replace(" ", "-")))
            urls.append(f"<url><loc>{SITE_URL}/producto/{slug}</loc><priority>0.8</priority><lastmod>{p.created_at.date().isoformat() if p.created_at else ''}</lastmod></url>")
        body = "\n".join(urls)
        return PlainTextResponse(
            f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{body}\n</urlset>',
            media_type="application/xml",
        )
    finally:
        db.close()


@fastapi_app.get("/api/config")
def app_config():
    return {
        "GA_ID": os.getenv("GA_MEASUREMENT_ID", ""),
        "META_PIXEL_ID": os.getenv("META_PIXEL_ID", ""),
        "SITE_URL": SITE_URL,
    }


@fastapi_app.get("/api/config/recaptcha")
def recaptcha_config():
    site_key = os.getenv("RECAPTCHA_SITE_KEY", "")
    return {"site_key": site_key, "enabled": bool(site_key)}


fastapi_app.include_router(auth.router, prefix="/api")
fastapi_app.include_router(coupons.router, prefix="/api")
fastapi_app.include_router(faqs.router, prefix="/api")
fastapi_app.include_router(orders.router, prefix="/api")
fastapi_app.include_router(payments.router, prefix="/api")
fastapi_app.include_router(wompi.router, prefix="/api")
fastapi_app.include_router(products.router, prefix="/api")
fastapi_app.include_router(users.router, prefix="/api")
fastapi_app.include_router(messages.router, prefix="/api")
fastapi_app.include_router(analytics.router, prefix="/api")
fastapi_app.include_router(upload.router, prefix="/api")
fastapi_app.include_router(chat.router, prefix="/api")
fastapi_app.include_router(admin.router, prefix="/api/admin")
fastapi_app.include_router(banners.router, prefix="/api")
fastapi_app.include_router(reviews.router, prefix="/api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    from events import init_socketio
    init_socketio(sio)
    Base.metadata.create_all(bind=engine)

    # Migración runtime: agregar columna guest_token si no existe
    _migrate_runtime()

    db = SessionLocal()

    admin_email = os.getenv("SEED_ADMIN_EMAIL", "")
    admin_pass = os.getenv("SEED_ADMIN_PASSWORD", "")
    if ENVIRONMENT == "production" and not (admin_email and admin_pass):
        raise RuntimeError(
            "SEED_ADMIN_EMAIL y SEED_ADMIN_PASSWORD deben configurarse en producción."
            " No se usan credenciales por defecto."
        )

    admin = db.query(User).filter(User.role == UserRole.admin.value).first()
    if admin:
        # Sync password hash with SEED_ADMIN_PASSWORD if it changed
        if admin_pass and not verify_password(admin_pass, admin.password_hash):
            admin.password_hash = hash_password(admin_pass)
            admin.failed_login_attempts = 0
            admin.locked_until = None
            logger.info("Admin password hash sincronizado con SEED_ADMIN_PASSWORD")
        else:
            logger.info("Admin ya existe — password OK")
    else:
        if not (admin_email and admin_pass):
            logger.warning("No se creó admin: faltan SEED_ADMIN_EMAIL/SEED_ADMIN_PASSWORD (solo dev)")
        else:
            admin = User(
                name="Admin Gracia",
                email=admin_email,
                password_hash=hash_password(admin_pass),
                role="admin",
            )
            db.add(admin)

    # Second admin (configurable via env vars)
    second_admin_email = os.getenv("SECOND_ADMIN_EMAIL", "")
    second_admin_pass = os.getenv("SECOND_ADMIN_PASSWORD", "")
    if second_admin_email and second_admin_pass:
        second_admin = db.query(User).filter(User.email == second_admin_email).first()
        if not second_admin:
            second_admin = User(
                name="Admin Secundario",
                email=second_admin_email,
                password_hash=hash_password(second_admin_pass),
                role="admin",
                email_verified=True,
            )
            db.add(second_admin)
            logger.info(f"Segundo admin creado: {second_admin_email}")
        else:
            if not verify_password(second_admin_pass, second_admin.password_hash):
                second_admin.password_hash = hash_password(second_admin_pass)
                second_admin.failed_login_attempts = 0
                second_admin.locked_until = None
                logger.info(f"Password del segundo admin sincronizado: {second_admin_email}")

    if ENVIRONMENT == "production":
        if not (os.getenv("SMTP_USER", "") and os.getenv("SMTP_PASS", "")):
            raise RuntimeError(
                "SMTP_USER y SMTP_PASS deben configurarse en producción para enviar "
                "confirmaciones de pedido y reseteos de contraseña. "
                "Referencia: https://myaccount.google.com/apppasswords (Gmail) o tu proveedor SMTP."
            )
        smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        logger.info(f"SMTP habilitado para envíos de email ({smtp_host})")

    db.commit()
    db.close()
    yield


def _migrate_runtime():
    """Agrega columnas nuevas a tablas existentes sin romper la DB (SQLite y Postgres)."""
    from sqlalchemy import text, inspect as sa_inspect

    with engine.connect() as conn:
        inspector = sa_inspect(conn)
        existing_tables = set(inspector.get_table_names())
        table_columns = {}
        for t in existing_tables:
            table_columns[t] = {c["name"] for c in inspector.get_columns(t)}

    for table_name, table_cols in Base.metadata.tables.items():
        if table_name not in existing_tables:
            continue
        existing_col_names = table_columns[table_name]
        for col in table_cols.columns:
            if col.name not in existing_col_names:
                col_type = col.type.compile(engine.dialect)
                ddl = f"ALTER TABLE {table_name} ADD COLUMN {col.name} {col_type}"
                try:
                    with engine.begin() as conn2:
                        conn2.execute(text(ddl))
                    logger.info(f"Migrated: added {table_name}.{col.name}")
                except Exception:
                    pass  # Column already exists or other non-critical error


fastapi_app.router.lifespan_context = lifespan


@fastapi_app.get("/health")
def health():
    return {"status": "ok", "app": "Gracia Clothing API", "version": "2.0.0"}
