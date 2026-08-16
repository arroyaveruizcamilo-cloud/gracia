from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import Order, OrderItem, OrderStatus, PaymentStatus, Coupon, Notification, User, UserRole
from schemas import OrderCreate
from auth import require_admin, get_optional_user
from services.email_service import send_order_confirmation, send_admin_new_order, send_order_status_update
from services.order_service import build_order_items, compute_coupon_discount, compute_shipping, reserve_stock, release_stock

router = APIRouter(prefix="/orders", tags=["Orders"])


def order_to_dict(o):
    return {
        "id": o.id,
        "user_id": o.user_id,
        "customer_name": o.customer_name,
        "customer_email": o.customer_email,
        "customer_phone": o.customer_phone,
        "shipping_address": o.shipping_address,
        "shipping_city": o.shipping_city,
        "shipping_state": o.shipping_state,
        "shipping_zip": o.shipping_zip,
        "shipping_cost": o.shipping_cost,
        "coupon_code": o.coupon_code,
        "discount": o.discount,
        "subtotal": o.subtotal,
        "total": o.total,
        "status": o.status.value if hasattr(o.status, "value") else o.status,
        "payment_status": o.payment_status.value if hasattr(o.payment_status, "value") else o.payment_status,
        "payment_method": o.payment_method,
        "payment_id": o.payment_id,
        "tracking_number": o.tracking_number,
        "notes": o.notes,
        "created_at": o.created_at.isoformat() if o.created_at else None,
        "items": [
            {
                "product_name": i.product_name,
                "variant_size": i.variant_size,
                "variant_color": i.variant_color,
                "quantity": i.quantity,
                "price": i.price,
            }
            for i in o.items
        ],
    }


@router.post("")
def create_order(data: OrderCreate, db: Session = Depends(get_db),
                 current_user: User | None = Depends(get_optional_user)):
    # Validate delivery city
    if not data.shipping_city or not data.shipping_city.strip():
        raise HTTPException(status_code=400, detail="La ciudad de entrega es obligatoria")

    # Los precios, subtotales y descuentos se calculan SIEMPRE en el servidor.
    # Cualquier valor enviado por el cliente es ignorado.
    items_data = build_order_items(db, data.items)

    subtotal = round(sum(it["price"] * it["quantity"] for it in items_data), 2)
    discount, coupon_code = compute_coupon_discount(db, data.coupon_code, subtotal)
    shipping_cost = compute_shipping(subtotal)
    total = round(subtotal - discount + shipping_cost, 2)

    name = data.customer_name or data.customer_email.split('@')[0] or 'Cliente'
    order = Order(
        user_id=current_user.id if current_user else None,
        customer_name=name,
        customer_email=data.customer_email,
        customer_phone=data.customer_phone,
        shipping_address=data.shipping_address,
        shipping_city=data.shipping_city,
        shipping_state=data.shipping_state,
        shipping_zip=data.shipping_zip,
        shipping_cost=shipping_cost,
        coupon_code=coupon_code,
        discount=discount,
        subtotal=subtotal,
        total=total,
        status=OrderStatus.pending,
        payment_status=PaymentStatus.pending,
        payment_method=data.payment_method,
        notes=data.notes,
    )
    db.add(order)

    # Reservar stock en la misma transacción (se revierte si la orden se cancela o falla)
    reserve_stock(db, items_data)
    db.flush()

    for it in items_data:
        item_fields = {k: v for k, v in it.items() if not k.startswith("_")}
        db.add(OrderItem(order_id=order.id, **item_fields))

    # Mark coupon as used (only if it was actually applied)
    if coupon_code:
        coupon = db.query(Coupon).filter(Coupon.code == coupon_code).first()
        if coupon:
            coupon.used_count += 1

    db.commit()
    db.refresh(order)

    # Send email confirmation to customer
    items_data_for_email = [
        {"product_name": it["product_name"], "quantity": it["quantity"], "price": it["price"]}
        for it in items_data
    ]
    send_order_confirmation(
        to=order.customer_email,
        order_id=order.id,
        items=items_data_for_email,
        total=order.total,
        customer_name=name,
        payment_method=data.payment_method,
    )

    # Notify admin (in-app + email)
    admins = db.query(User).filter(User.role == UserRole.admin.value).all()
    for admin in admins:
        notif = Notification(
            user_id=admin.id, type="new_order",
            title="Nuevo Pedido",
            body=f"Pedido #{order.id} por {order.customer_name} — ${order.total:.2f}",
        )
        db.add(notif)
        send_admin_new_order(
            to=admin.email,
            order_id=order.id,
            customer_name=order.customer_name,
            customer_email=order.customer_email,
            total=order.total,
            items=items_data_for_email,
        )
    db.commit()

    return {"message": "Pedido creado", "order_id": order.id, "total": order.total}


@router.get("")
def list_orders(db: Session = Depends(get_db), admin=Depends(require_admin)):
    orders = db.query(Order).order_by(Order.created_at.desc()).all()
    return [order_to_dict(o) for o in orders]


@router.get("/{order_id}")
def get_order(order_id: int, db: Session = Depends(get_db), admin=Depends(require_admin)):
    o = db.query(Order).filter(Order.id == order_id).first()
    if not o:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")
    return order_to_dict(o)


@router.put("/{order_id}/status")
def update_order_status(order_id: int, data: dict, db: Session = Depends(get_db), admin=Depends(require_admin)):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")

    if "status" in data:
        valid_statuses = [s.value for s in OrderStatus]
        if data["status"] not in valid_statuses:
            raise HTTPException(status_code=400, detail=f"Estados válidos: {valid_statuses}")
        order.status = data["status"]
        # Liberar stock reservado si la orden se cancela
        if data["status"] == OrderStatus.cancelled.value:
            release_stock(db, order)

    if "payment_status" in data:
        valid_payment = [s.value for s in PaymentStatus]
        if data["payment_status"] not in valid_payment:
            raise HTTPException(status_code=400, detail=f"Estados válidos: {valid_payment}")
        order.payment_status = data["payment_status"]
        # Si el pago se marca como fallido/reembolsado, liberar stock
        if data["payment_status"] in (PaymentStatus.failed.value, PaymentStatus.refunded.value):
            release_stock(db, order)

    if "tracking_number" in data:
        order.tracking_number = data["tracking_number"]

    db.commit()

    # Notify customer of status change
    if "status" in data:
        db.refresh(order)
        notif = Notification(
            user_id=order.user_id, type="order_status",
            title="Estado del pedido actualizado",
            body=f"Tu pedido #{order.id} ahora está: {order.status}",
        )
        db.add(notif)
        db.commit()
        if order.customer_email:
            send_order_status_update(
                to=order.customer_email,
                order_id=order.id,
                status=order.status.value if hasattr(order.status, "value") else order.status,
                customer_name=order.customer_name,
                tracking_number=order.tracking_number or "",
            )

    return {"message": "Pedido actualizado"}


@router.put("/{order_id}/tracking")
def update_tracking(order_id: int, data: dict, db: Session = Depends(get_db), admin=Depends(require_admin)):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")
    order.tracking_number = data.get("tracking_number", order.tracking_number)
    db.commit()
    return {"message": "Tracking actualizado"}


# For customers: get their own order by ID (with tracking info)
@router.get("/track/{order_id}")
def track_order(order_id: int, email: str = "", db: Session = Depends(get_db)):
    o = db.query(Order).filter(Order.id == order_id).first()
    if not o:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")
    if email and o.customer_email != email:
        raise HTTPException(status_code=403, detail="Email no coincide con el pedido")
    return {
        "id": o.id,
        "status": o.status.value if hasattr(o.status, "value") else o.status,
        "payment_status": o.payment_status.value if hasattr(o.payment_status, "value") else o.payment_status,
        "tracking_number": o.tracking_number,
        "total": o.total,
        "created_at": o.created_at.isoformat() if o.created_at else None,
        "items": [{"product_name": i.product_name, "quantity": i.quantity} for i in o.items],
    }
