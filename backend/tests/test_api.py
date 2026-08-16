"""Tests para la API de GRACIA."""

import os
import sys
import tempfile
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Desactivar límites de rate limiting durante los tests (se leen al importar)
os.environ.setdefault("RATE_LIMIT_REGISTER", "200")
os.environ.setdefault("RATE_LIMIT_LOGIN", "200")
os.environ.setdefault("RATE_LIMIT_FORGOT", "200")
os.environ.setdefault("RATE_LIMIT_RESET", "200")
os.environ.setdefault("ENVIRONMENT", "development")

_db_fd, _db_path = tempfile.mkstemp(suffix=".db")
os.environ["DATABASE_URL"] = f"sqlite:///{_db_path}"

import database
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

database.engine = create_engine(f"sqlite:///{_db_path}", connect_args={"check_same_thread": False})
database.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=database.engine)

from models import Base, User, Address, Product, ProductVariant
from main import fastapi_app

app = fastapi_app

def _seed_test_data():
    from database import SessionLocal
    from models import Category
    db = SessionLocal()
    Base.metadata.create_all(bind=db.bind)
    # Seed categories if needed
    if db.query(Category).count() == 0:
        cats = [
            Category(name="Vestidos", slug="vestidos"),
            Category(name="Blusas", slug="blusas"),
        ]
        for c in cats: db.add(c)
        db.flush()
    if db.query(Product).count() == 0:
        p1 = Product(name="Vestido Test", slug="vestido-test", price=100.0, category="Vestidos", category_id=1, stock=10, status="active")
        p2 = Product(name="Blusa Test", slug="blusa-test", price=50.0, category="Blusas", category_id=2, stock=5, status="active")
        db.add(p1); db.add(p2); db.flush()
        db.add(ProductVariant(product_id=p1.id, size="M", color="Negro", stock=10))
        db.add(ProductVariant(product_id=p2.id, size="L", color="Negro", stock=5))
        db.commit()
    db.close()

_seed_test_data()

client = TestClient(app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_list_products():
    resp = client.get("/api/products")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 2


def test_get_product():
    resp = client.get("/api/products/1")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Vestido Test"


def test_register():
    resp = client.post("/api/auth/register", json={
        "name": "Test User",
        "email": "test@example.com",
        "password": "TestPass123",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["user"]["email"] == "test@example.com"


def test_login():
    resp = client.post("/api/auth/login", json={
        "email": "test@example.com",
        "password": "TestPass123",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data


def test_me():
    # Login as the user created in test_register (or register now)
    resp = client.post("/api/auth/login", json={
        "email": "test@example.com",
        "password": "TestPass123",
    })
    if resp.status_code != 200:
        # Register first
        resp = client.post("/api/auth/register", json={
            "name": "Test User", "email": "test@example.com", "password": "TestPass123",
        })
    token = resp.json()["access_token"]

    resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "test@example.com"


def test_cart_flow():
    resp = client.post("/api/auth/register", json={
        "name": "Cart User",
        "email": "cart@example.com",
        "password": "CartPass123",
    })
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Get product id
    products = client.get("/api/products").json()
    pid = products[0]["id"]

    # Add to cart
    resp = client.post("/api/users/cart", json={"product_id": pid, "quantity": 1}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["message"] == "Añadido al carrito"

    # Get cart
    resp = client.get("/api/users/cart", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) >= 0


def test_create_order():
    resp = client.post("/api/auth/register", json={
        "name": "Order User", "email": "order@example.com", "password": "Order123!",
    })
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    products = client.get("/api/products").json()
    pid = products[0]["id"]

    resp = client.post("/api/orders", json={
        "customer_email": "order@example.com",
        "customer_name": "Order User",
        "shipping_address": "Calle 1 #2-3",
        "shipping_city": "Bogotá",
        "payment_method": "cod",
        "items": [{"product_id": pid, "quantity": 1, "price": 100.0}],
    }, headers=headers)
    assert resp.status_code == 200
    assert "order_id" in resp.json()


def test_faqs():
    resp = client.get("/api/faqs")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_payment_methods():
    resp = client.get("/api/payments/methods")
    assert resp.status_code == 200
    data = resp.json()
    assert "methods" in data


# ─── Seguridad: precios del lado del servidor ────────────────
def _register(name, email):
    resp = client.post("/api/auth/register", json={
        "name": name, "email": email, "password": "TestPass123",
    })
    assert resp.status_code == 200
    return resp.json()["access_token"]


def _get_product_stock(pid):
    from database import SessionLocal
    from models import Product
    db = SessionLocal()
    try:
        return db.query(Product).filter(Product.id == pid).first().stock
    finally:
        db.close()


def test_order_ignores_client_price():
    token = _register("Precio User", "precio@example.com")
    products = client.get("/api/products").json()
    pid = products[0]["id"]
    real_price = next(p["price"] for p in products if p["id"] == pid)

    resp = client.post("/api/orders", json={
        "customer_email": "precio@example.com",
        "customer_name": "Precio User",
        "shipping_address": "Calle 1",
        "shipping_city": "Bogotá",
        "payment_method": "card",
        "subtotal": 0.01,
        "discount": 99999,
        "total": 0.01,
        "items": [{"product_id": pid, "quantity": 1, "price": 0.01}],
    }, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == real_price, f"Total debería ser {real_price}, fue {data['total']}"


def test_order_with_coupon_discount_server_side():
    from database import SessionLocal
    from models import Coupon
    db = SessionLocal()
    db.add(Coupon(code="TEST10", discount_type="percentage", discount_value=10,
                  min_purchase=0, usage_limit=100, is_active=True))
    db.commit()
    db.close()

    token = _register("Coupon User", "coupon@example.com")
    products = client.get("/api/products").json()
    pid = products[0]["id"]
    real_price = next(p["price"] for p in products if p["id"] == pid)

    resp = client.post("/api/orders", json={
        "customer_email": "coupon@example.com",
        "customer_name": "Coupon User",
        "shipping_address": "Calle 1",
        "shipping_city": "Bogotá",
        "payment_method": "card",
        "coupon_code": "TEST10",
        "items": [{"product_id": pid, "quantity": 1, "price": 9999}],
    }, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["total"] == round(real_price * 0.9, 2)


def test_order_invalid_coupon_ignored():
    token = _register("BadCoupon User", "badcoupon@example.com")
    products = client.get("/api/products").json()
    pid = products[0]["id"]
    real_price = next(p["price"] for p in products if p["id"] == pid)

    resp = client.post("/api/orders", json={
        "customer_email": "badcoupon@example.com",
        "customer_name": "BadCoupon User",
        "shipping_address": "Calle 1",
        "shipping_city": "Bogotá",
        "payment_method": "card",
        "coupon_code": "NOEXISTE",
        "discount": 99999,
        "items": [{"product_id": pid, "quantity": 1, "price": 0.01}],
    }, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["total"] == real_price


# ─── Stock: reserva y liberación ─────────────────────────────
def _make_admin(email):
    from database import SessionLocal
    from models import User
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            user = User(name="Admin Test", email=email,
                        password_hash="x", role="admin")
            db.add(user)
        user.role = "admin"
        db.commit()
    finally:
        db.close()


def test_stock_reserved_and_released_on_cancel():
    token = _register("Stock User", "stock@example.com")
    admin_token = _register("Admin Log", "admin2@example.com")
    _make_admin("admin2@example.com")

    products = client.get("/api/products").json()
    pid = products[0]["id"]
    before = _get_product_stock(pid)

    resp = client.post("/api/orders", json={
        "customer_email": "stock@example.com",
        "customer_name": "Stock User",
        "shipping_address": "Calle 1",
        "shipping_city": "Bogotá",
        "payment_method": "card",
        "items": [{"product_id": pid, "quantity": 2, "price": 0.01}],
    }, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    order_id = resp.json()["order_id"]
    assert _get_product_stock(pid) == before - 2

    # Admin cancela la orden → el stock se libera
    resp = client.post("/api/admin/order/status", json={
        "id": order_id, "status": "Cancelado",
    }, headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    assert _get_product_stock(pid) == before


def test_order_stock_insufficient_rejected():
    token = _register("LowStock User", "lowstock@example.com")
    products = client.get("/api/products").json()
    pid = products[1]["id"]
    resp = client.post("/api/orders", json={
        "customer_email": "lowstock@example.com",
        "customer_name": "LowStock User",
        "shipping_address": "Calle 1",
        "shipping_city": "Bogotá",
        "payment_method": "card",
        "items": [{"product_id": pid, "quantity": 9999, "price": 1}],
    }, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 400


import atexit
atexit.register(lambda: (os.close(_db_fd), os.unlink(_db_path)) if os.path.exists(_db_path) else None)
