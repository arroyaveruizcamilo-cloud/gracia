from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import Order, OrderItem, Product, ProductVariant, OrderStatus, PaymentStatus, Coupon, Notification, User, UserRole
from schemas import OrderCreate
from auth import require_admin, get_current_user, get_optional_user
from services.email_service import send_order_confirmation, send_admin_new_order, send_order_status_update

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
    if not data.items:
        raise HTTPException(status_code=400, detail="No hay productos en el pedido")

    # Validate delivery city
    if not data.shipping_city or not data.shipping_city.strip():
        raise HTTPException(status_code=400, detail="La ciudad de entrega es obligatoria")

    total = data.subtotal if data.subtotal > 0 else 0
    items_data = []

    for item_data in data.items:
        product = db.query(Product).filter(Product.id == item_data.product_id).first()
        if not product or product.status != "active":
            continue

        # Check variant stock if specified
        if item_data.variant_size or item_data.variant_color:
            variant = db.query(ProductVariant).filter(
                ProductVariant.product_id == product.id,
                ProductVariant.size == item_data.variant_size,
                ProductVariant.color == item_data.variant_color,
            ).first()
            if variant:
                if variant.stock < item_data.quantity:
                    raise HTTPException(status_code=400,
                                        detail=f"Stock insuficiente para {product.name} ({item_data.variant_size}/{item_data.variant_color})")
                variant.stock -= item_data.quantity
                price = item_data.price if item_data.price > 0 else (variant.price_override or product.price)
            else:
                price = item_data.price if item_data.price > 0 else product.price
        else:
            if product.stock < item_data.quantity:
                raise HTTPException(status_code=400,
                                    detail=f"Stock insuficiente para {product.name}")
            product.stock -= item_data.quantity
            price = item_data.price if item_data.price > 0 else product.price

        items_data.append({
            "product_id": product.id,
            "product_name": product.name,
            "variant_size": item_data.variant_size,
            "variant_color": item_data.variant_color,
            "quantity": item_data.quantity,
            "price": price,
        })

    if not items_data:
        raise HTTPException(status_code=400, detail="No hay productos válidos en el pedido")

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
        shipping_cost=data.shipping_cost,
        coupon_code=data.coupon_code,
        discount=data.discount,
        subtotal=data.subtotal,
        total=data.total or total + data.shipping_cost - data.discount,
        status=OrderStatus.pending,
        payment_status=PaymentStatus.pending,
        payment_method=data.payment_method,
        notes=data.notes,
    )
    db.add(order)
    db.flush()

    for it in items_data:
        db.add(OrderItem(order_id=order.id, **it))

    # Mark coupon as used
    if data.coupon_code:
        coupon = db.query(Coupon).filter(Coupon.code == data.coupon_code).first()
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

    if "payment_status" in data:
        valid_payment = [s.value for s in PaymentStatus]
        if data["payment_status"] not in valid_payment:
            raise HTTPException(status_code=400, detail=f"Estados válidos: {valid_payment}")
        order.payment_status = data["payment_status"]

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
