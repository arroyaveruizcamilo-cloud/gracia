"""Servicios de órdenes: precios calculados en servidor, reserva y liberación de stock."""
import os
import logging
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from models import Product, ProductVariant, Coupon, Order

logger = logging.getLogger("gracia.orders")


# ─── Precios del lado del servidor ───────────────────────────
def build_order_items(db: Session, items: list):
    """Valida los ítems contra la BD y devuelve precios calculados en el servidor.

    Ignora por completo los precios/cantidades enviados por el cliente (solo se usa
    product_id, variante y cantidad para identificar el producto).
    """
    if not items:
        raise HTTPException(status_code=400, detail="No hay productos en el pedido")

    items_data = []
    for item_data in items:
        quantity = item_data.quantity
        if quantity is None or quantity <= 0:
            raise HTTPException(status_code=400, detail="Cantidad inválida")

        product = db.query(Product).filter(Product.id == item_data.product_id).first()
        if not product or product.status != "active":
            raise HTTPException(status_code=400, detail="Producto no disponible")

        variant = None
        if item_data.variant_size or item_data.variant_color:
            variant = db.query(ProductVariant).filter(
                ProductVariant.product_id == product.id,
                ProductVariant.size == item_data.variant_size,
                ProductVariant.color == item_data.variant_color,
            ).first()
            if not variant:
                raise HTTPException(
                    status_code=400,
                    detail=f"Variante no encontrada para {product.name} ({item_data.variant_size}/{item_data.variant_color})",
                )
            if variant.stock < quantity:
                raise HTTPException(
                    status_code=400,
                    detail=f"Stock insuficiente para {product.name} ({item_data.variant_size}/{item_data.variant_color})",
                )
        else:
            if product.stock < quantity:
                raise HTTPException(
                    status_code=400,
                    detail=f"Stock insuficiente para {product.name}",
                )

        price = variant.price_override if (variant and variant.price_override) else product.price

        items_data.append({
            "product_id": product.id,
            "product_name": product.name,
            "variant_size": item_data.variant_size,
            "variant_color": item_data.variant_color,
            "quantity": quantity,
            "price": round(float(price), 2),
            "_variant": variant,
            "_product": product,
        })
    return items_data


def compute_coupon_discount(db: Session, coupon_code: str, subtotal: float) -> tuple[float, str]:
    """Valida el cupón en el servidor y devuelve (descuento, código_normalizado)."""
    code = (coupon_code or "").strip().upper()
    if not code:
        return 0.0, ""

    coupon = db.query(Coupon).filter(Coupon.code == code, Coupon.is_active == True).first()
    if not coupon:
        return 0.0, ""
    if coupon.usage_limit > 0 and coupon.used_count >= coupon.usage_limit:
        return 0.0, ""
    if coupon.expires_at and coupon.expires_at < datetime.now():
        return 0.0, ""

    if subtotal < coupon.min_purchase:
        return 0.0, ""

    discount = (subtotal * coupon.discount_value / 100) if coupon.discount_type == "percentage" else coupon.discount_value
    if coupon.max_discount and discount > coupon.max_discount:
        discount = coupon.max_discount
    discount = min(max(discount, 0.0), subtotal)
    return round(float(discount), 2), code


def compute_shipping(subtotal: float) -> float:
    """Costo de envío calculado en el servidor (configurable por env)."""
    cost = float(os.getenv("SHIPPING_COST", "0"))
    free_min = float(os.getenv("FREE_SHIPPING_MIN", "0"))
    if free_min > 0 and subtotal >= free_min:
        return 0.0
    return round(cost, 2)


# ─── Stock ───────────────────────────────────────────────────
def reserve_stock(db: Session, items_data: list):
    """Descuenta stock al crear la orden (reserva). Se revierte con release_stock."""
    for it in items_data:
        if it["_variant"] is not None:
            it["_variant"].stock -= it["quantity"]
        else:
            it["_product"].stock -= it["quantity"]


def release_stock(db: Session, order: Order) -> bool:
    """Devuelve el stock reservado por una orden. Idempotente.

    Se invoca cuando el pago falla, se reembolsa, o la orden se cancela.
    """
    if getattr(order, "stock_released", False):
        return False
    if not order.items:
        return False

    for item in order.items:
        product = db.query(Product).filter(Product.id == item.product_id).first()
        if not product:
            continue
        if item.variant_size or item.variant_color:
            variant = db.query(ProductVariant).filter(
                ProductVariant.product_id == item.product_id,
                ProductVariant.size == item.variant_size,
                ProductVariant.color == item.variant_color,
            ).first()
            if variant:
                variant.stock += item.quantity
        else:
            product.stock += item.quantity

    order.stock_released = True
    return True
