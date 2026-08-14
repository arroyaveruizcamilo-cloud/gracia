from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import get_db
from models import Order, OrderItem, Product, Message, OrderStatus
from auth import require_admin

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db), admin=Depends(require_admin)):
    total_orders = db.query(Order).count()

    total_revenue = db.query(func.coalesce(func.sum(Order.total), 0)).filter(
        Order.status.in_([OrderStatus.delivered.value, OrderStatus.shipped.value, OrderStatus.processing.value])
    ).scalar()

    total_products = db.query(Product).filter(Product.status == "active").count()
    total_messages = db.query(Message).count()

    low_stock = db.query(Product).filter(Product.stock < 10, Product.status == "active").count()

    recent_orders = (
        db.query(Order).order_by(Order.created_at.desc()).limit(5).all()
    )
    recent = [
        {
            "id": o.id,
            "customer": o.customer_name,
            "total": o.total,
            "status": o.status.value if hasattr(o.status, "value") else o.status,
            "date": o.created_at.isoformat() if o.created_at else None,
        }
        for o in recent_orders
    ]

    return {
        "total_orders": total_orders,
        "total_revenue": float(total_revenue),
        "total_products": total_products,
        "total_messages": total_messages,
        "low_stock": low_stock,
        "recent_orders": recent,
    }


@router.get("/sales")
def sales(db: Session = Depends(get_db), admin=Depends(require_admin)):
    orders = db.query(Order).filter(Order.status != OrderStatus.cancelled).all()
    monthly = {}
    for o in orders:
        if o.created_at:
            key = o.created_at.strftime("%Y-%m")
            if key not in monthly:
                monthly[key] = {"month": key, "revenue": 0.0, "orders": 0}
            monthly[key]["revenue"] += o.total
            monthly[key]["orders"] += 1
    result = sorted(monthly.values(), key=lambda x: x["month"])
    return result


@router.get("/products")
def top_products(db: Session = Depends(get_db), admin=Depends(require_admin)):
    top = (
        db.query(
            OrderItem.product_name,
            func.sum(OrderItem.quantity).label("total_qty"),
            func.sum(OrderItem.price * OrderItem.quantity).label("total_revenue"),
        )
        .group_by(OrderItem.product_name)
        .order_by(func.sum(OrderItem.quantity).desc())
        .limit(10)
        .all()
    )
    return [
        {
            "name": t.product_name,
            "quantity": int(t.total_qty),
            "revenue": float(t.total_revenue),
        }
        for t in top
    ]
