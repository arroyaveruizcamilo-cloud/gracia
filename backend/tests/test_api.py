"""Tests para la API de GRACIA."""

import os
import sys
import tempfile
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

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


import atexit
atexit.register(lambda: (os.close(_db_fd), os.unlink(_db_path)) if os.path.exists(_db_path) else None)
