import sys
import os
import logging
from pathlib import Path
from contextlib import asynccontextmanager

sys.path.append(str(Path(__file__).resolve().parent))

import sentry_sdk
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, PlainTextResponse
from database import engine, Base, SessionLocal
from models import User, Product, ProductVariant, FAQ, Coupon
from auth import hash_password
from middleware.error_handler import global_error_handler
import socketio

SENTRY_DSN = os.getenv("SENTRY_DSN", "")
if SENTRY_DSN:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        environment=os.getenv("ENVIRONMENT", "development"),
        traces_sample_rate=0.1,
    )

from routers import (
    auth, products, orders, analytics, messages, users, coupons,
    faqs, payments, upload, chat, admin, banners, reviews,
)

ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("gracia")

sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")
fastapi_app = FastAPI(title="Gracia Clothing API", version="2.0.0")
app = socketio.ASGIApp(sio, other_asgi_app=fastapi_app)

# ─── Production middleware ────────────────────────────────
allowed_origins_str = os.getenv("CORS_ORIGINS", "*")
allowed_origins = allowed_origins_str.split(",") if allowed_origins_str != "*" else ["*"]
fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins if ENVIRONMENT == "production" else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if ENVIRONMENT == "production":
    fastapi_app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=allowed_origins,
    )

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


@fastapi_app.get("/robots.txt")
def robots():
    return PlainTextResponse("""User-agent: *
Allow: /
Sitemap: https://graciaclothing.com/sitemap.xml
""")


@fastapi_app.get("/producto/{slug}")
def serve_product(slug: str):
    return FileResponse(FRONTEND_DIR / "index.html")


@fastapi_app.get("/sitemap.xml")
def sitemap():
    return PlainTextResponse("""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://graciaclothing.com/</loc><priority>1.0</priority></url>
  <url><loc>https://graciaclothing.com/#nuevo</loc><priority>0.9</priority></url>
  <url><loc>https://graciaclothing.com/#coleccion</loc><priority>0.8</priority></url>
  <url><loc>https://graciaclothing.com/#faq-sec</loc><priority>0.6</priority></url>
</urlset>
""", media_type="application/xml")


fastapi_app.include_router(auth.router, prefix="/api")
fastapi_app.include_router(coupons.router, prefix="/api")
fastapi_app.include_router(faqs.router, prefix="/api")
fastapi_app.include_router(orders.router, prefix="/api")
fastapi_app.include_router(payments.router, prefix="/api")
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
    db = SessionLocal()

    admin_email = os.getenv("SEED_ADMIN_EMAIL", "admin@gracia.moda")
    admin_pass = os.getenv("SEED_ADMIN_PASSWORD", "Admin123!")
    admin = db.query(User).filter(User.email == admin_email).first()
    if not admin:
        admin = User(
            name="Admin Gracia",
            email=admin_email,
            password_hash=hash_password(admin_pass),
            role="admin",
        )
        db.add(admin)
        db.commit()

    seed_products(db)
    seed_faqs(db)

    if not db.query(Coupon).first():
        db.add(Coupon(code="GRACIA10", discount_type="percentage", discount_value=10, min_purchase=50, usage_limit=100, is_active=True))
        db.add(Coupon(code="BIENVENIDA", discount_type="percentage", discount_value=15, min_purchase=30, usage_limit=200, is_active=True))
        db.commit()

    db.close()
    yield


fastapi_app.router.lifespan_context = lifespan


def seed_products(db):
    if db.query(Product).count() > 0:
        return
    items = [
        {"name": "Vestido Floral Primavera", "name_en": "Spring Floral Dress", "description": "Vestido largo con estampado floral, ideal para ocasiones especiales.", "description_en": "Long dress with floral print, ideal for special occasions.", "price": 149.99, "old_price": 199.99, "category": "Vestidos", "category_en": "Dresses", "stock": 25, "image": "https://images.unsplash.com/photo-1595777457583-95e059d581b8?w=500", "featured": True, "badge": "Nuevo"},
        {"name": "Blusa Seda Elegante", "name_en": "Elegant Silk Blouse", "description": "Blusa de seda natural con corte moderno.", "description_en": "Natural silk blouse with modern cut.", "price": 89.99, "old_price": None, "category": "Blusas", "category_en": "Blouses", "stock": 30, "image": "https://images.unsplash.com/photo-1596755094514-f87e34085b2c?w=500", "featured": True},
        {"name": "Corset Cuero Premium", "name_en": "Premium Leather Corset", "description": "Corset de cuero genuino con cierre trasero.", "description_en": "Genuine leather corset with back closure.", "price": 129.99, "old_price": 169.99, "category": "Corsets", "category_en": "Corsets", "stock": 15, "image": "https://images.unsplash.com/photo-1591382386627-349b69288d2c?w=500", "featured": False, "badge": "Exclusivo"},
        {"name": "Pantalón Palazzo", "name_en": "Palazzo Pants", "description": "Pantalón ancho tipo palazzo, fresco y elegante.", "description_en": "Wide palazzo style pants, fresh and elegant.", "price": 79.99, "old_price": None, "category": "Pantalones", "category_en": "Pants", "stock": 40, "image": "https://images.unsplash.com/photo-1594633312681-425c7b97ccd1?w=500", "featured": True},
        {"name": "Body Encaje Negro", "name_en": "Black Lace Bodysuit", "description": "Body de encaje negro con transparencias.", "description_en": "Black lace bodysuit with sheer details.", "price": 59.99, "old_price": 79.99, "category": "Bodies", "category_en": "Bodysuits", "stock": 20, "image": "https://images.unsplash.com/photo-1608236415058-d4e35e73e9f7?w=500", "featured": False},
        {"name": "Falda Plisada", "name_en": "Pleated Skirt", "description": "Falda plisada hasta la rodilla, color nude.", "description_en": "Knee-length pleated skirt, nude color.", "price": 69.99, "old_price": None, "category": "Faldas", "category_en": "Skirts", "stock": 35, "image": "https://images.unsplash.com/photo-1583496661160-fb5886a0aaaa?w=500", "featured": False},
        {"name": "Buzo Oversize", "name_en": "Oversize Sweatshirt", "description": "Buzo algodón oversize con capucha.", "description_en": "Oversize cotton hoodie.", "price": 64.99, "old_price": 84.99, "category": "Buzos", "category_en": "Sweatshirts", "stock": 50, "image": "https://images.unsplash.com/photo-1556821840-3a63f95609a7?w=500", "featured": False},
        {"name": "Vestido Noche Glamour", "name_en": "Glamour Evening Dress", "description": "Vestido de noche con lentejuelas.", "description_en": "Evening dress with sequins.", "price": 249.99, "old_price": 329.99, "category": "Vestidos", "category_en": "Dresses", "stock": 10, "image": "https://images.unsplash.com/photo-1566174053879-31528523f8ae?w=500", "featured": True, "badge": "Ed. Limitada"},
        {"name": "Blusa Crop Top", "name_en": "Crop Top Blouse", "description": "Blusa corta con mangas abullonadas.", "description_en": "Cropped blouse with puff sleeves.", "price": 49.99, "old_price": None, "category": "Blusas", "category_en": "Blouses", "stock": 45, "image": "https://images.unsplash.com/photo-1576566588028-4147f3842f27?w=500", "featured": False},
        {"name": "Corset Floral", "name_en": "Floral Corset", "description": "Corset con bordados florales.", "description_en": "Corset with floral embroidery.", "price": 109.99, "old_price": 139.99, "category": "Corsets", "category_en": "Corsets", "stock": 12, "image": "https://images.unsplash.com/photo-1591228127791-8e2eaef5e3e1?w=500", "featured": False},
        {"name": "Pantalón Jeans Recto", "name_en": "Straight Jeans", "description": "Jeans recto clásico tiro alto.", "description_en": "Classic high-waist straight jeans.", "price": 69.99, "old_price": None, "category": "Pantalones", "category_en": "Pants", "stock": 60, "image": "https://images.unsplash.com/photo-1541099649105-f69ad21f3246?w=500", "featured": False},
        {"name": "Body Deportivo", "name_en": "Sport Bodysuit", "description": "Body transpirable para entrenar.", "description_en": "Breathable workout bodysuit.", "price": 44.99, "old_price": 59.99, "category": "Bodies", "category_en": "Bodysuits", "stock": 55, "image": "https://images.unsplash.com/photo-1518314911000-93e5ef2d26d0?w=500", "featured": False},
        {"name": "Falda Larga Boho", "name_en": "Boho Long Skirt", "description": "Falda larga estilo boho con vuelo.", "description_en": "Long boho style skirt with flare.", "price": 74.99, "old_price": None, "category": "Faldas", "category_en": "Skirts", "stock": 28, "image": "https://images.unsplash.com/photo-1583496661160-fb5886a0aaaa?w=500", "featured": False},
        {"name": "Buzo Cropped", "name_en": "Cropped Sweatshirt", "description": "Buzo corto con cremallera.", "description_en": "Cropped zip-up hoodie.", "price": 54.99, "old_price": 69.99, "category": "Buzos", "category_en": "Sweatshirts", "stock": 32, "image": "https://images.unsplash.com/photo-1556821840-3a63f95609a7?w=500", "featured": False},
    ]
    for it in items:
        p = Product(**it)
        db.add(p)
        db.flush()

        sizes = ["XS", "S", "M", "L", "XL"]
        for size in sizes[:3]:
            db.add(ProductVariant(product_id=p.id, size=size, color="Negro",
                                  color_hex="#000000", stock=5))
            db.add(ProductVariant(product_id=p.id, size=size, color="Blanco",
                                  color_hex="#FFFFFF", stock=5))

    db.commit()


def seed_faqs(db):
    if db.query(FAQ).count() > 0:
        return
    faqs_data = [
        {"question": "¿Cuánto tiempo tarda el envío?", "answer": "Los envíos tardan entre 3-7 días hábiles dependiendo de tu ubicación.", "category": "envíos"},
        {"question": "¿Aceptan devoluciones?", "answer": "Sí, aceptamos devoluciones dentro de los primeros 15 días. El producto debe estar en su estado original con etiquetas.", "category": "devoluciones"},
        {"question": "¿Cómo sé mi talla?", "answer": "Puedes consultar nuestra guía de tallas en la página de cada producto. Si tienes dudas, contáctanos por WhatsApp.", "category": "productos"},
        {"question": "¿Qué métodos de pago aceptan?", "answer": "Aceptamos Tarjeta Débito/Crédito (Visa, Mastercard, Amex), PSE (Bancolombia, Davivienda, Caja Social), Nequi, Daviplata, Llave Davivienda y SisteCrédito. Todos los pagos son procesados de forma segura por MercadoPago.", "category": "pagos"},
        {"question": "¿Hacen envíos internacionales?", "answer": "Por el momento solo realizamos envíos dentro del país. Pronto expandiremos.", "category": "envíos"},
    ]
    for f in faqs_data:
        db.add(FAQ(**f))
    db.commit()


@fastapi_app.get("/health")
def health():
    return {"status": "ok", "app": "Gracia Clothing API", "version": "2.0.0"}
