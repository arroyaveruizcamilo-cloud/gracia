from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, cast, Date, extract
from database import get_db
from models import (
    User, Product, Order, OrderItem, OrderTimeline,
    Message, Notification, ActivityLog, Category, Collection, Coupon,
    Banner, Review, NewsletterSubscriber
)
from schemas import OrderStatusRequest, NotifSendRequest, CategoryRequest, CollectionRequest
from auth import require_admin, get_current_user
from datetime import datetime, timedelta, timezone
from utils import db_to_dict as row_to_dict

router = APIRouter()


# ─── Dashboard Stats ─────────────────────────────────────────
@router.get("/stats")
async def admin_stats(admin=Depends(require_admin), db: Session = Depends(get_db)):
    now_dt = datetime.now(timezone.utc)
    today_start = now_dt.replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = now_dt - timedelta(days=7)
    month_ago = now_dt - timedelta(days=30)
    year_ago = now_dt - timedelta(days=365)

    total_orders = db.query(func.count(Order.id)).scalar() or 0
    total_revenue = db.query(func.coalesce(func.sum(Order.total), 0)).scalar()
    total_users = db.query(func.count(User.id)).scalar() or 0
    total_products = db.query(func.count(Product.id)).scalar() or 0
    pending_orders = db.query(func.count(Order.id)).filter(
        Order.status.in_(["Pendiente", "Procesando", "Confirmado"])
    ).scalar() or 0
    today_revenue = db.query(func.coalesce(func.sum(Order.total), 0)).filter(
        Order.created_at >= today_start
    ).scalar()
    week_revenue = db.query(func.coalesce(func.sum(Order.total), 0)).filter(
        Order.created_at >= week_ago
    ).scalar()
    month_revenue = db.query(func.coalesce(func.sum(Order.total), 0)).filter(
        Order.created_at >= month_ago
    ).scalar()
    year_revenue = db.query(func.coalesce(func.sum(Order.total), 0)).filter(
        Order.created_at >= year_ago
    ).scalar()
    orders_this_month = db.query(func.count(Order.id)).filter(
        Order.created_at >= month_ago
    ).scalar() or 0
    new_users_30 = db.query(func.count(User.id)).filter(
        User.created_at >= month_ago
    ).scalar() or 0

    today_orders = db.query(func.count(Order.id)).filter(
        Order.created_at >= today_start
    ).scalar() or 0
    completed_orders = db.query(func.count(Order.id)).filter(
        Order.status == "Entregado"
    ).scalar() or 0

    avg_order = db.query(func.coalesce(func.avg(Order.total), 0)).filter(
        Order.status != "Cancelado"
    ).scalar()

    active_users = db.query(func.count(func.distinct(Order.user_id))).filter(
        Order.created_at >= month_ago
    ).scalar() or 0

    total_cart = db.query(func.count(Order.id)).scalar() or 0
    completed_checkout = db.query(func.count(Order.id)).filter(
        Order.status != "Pendiente"
    ).scalar() or 0
    conversion_rate = round((completed_checkout / total_cart * 100) if total_cart > 0 else 0, 2)

    top_products = db.query(
        Product.id, Product.name, Product.image, Product.price,
        func.coalesce(func.sum(OrderItem.quantity), 0).label("total_sold"),
        func.coalesce(func.sum(OrderItem.quantity * OrderItem.price), 0).label("total_revenue"),
    ).outerjoin(OrderItem, Product.id == OrderItem.product_id
    ).group_by(Product.id).order_by(func.sum(OrderItem.quantity).desc().nulls_last()).limit(10).all()

    bottom_products = db.query(
        Product.id, Product.name, Product.image, Product.price,
        func.coalesce(func.sum(OrderItem.quantity), 0).label("total_sold"),
    ).outerjoin(OrderItem, Product.id == OrderItem.product_id
    ).group_by(Product.id).order_by(func.sum(OrderItem.quantity).asc().nulls_first()).limit(10).all()

    daily = []
    for i in range(6, -1, -1):
        day = (now_dt - timedelta(days=i)).strftime("%d/%m")
        day_start_dt = (now_dt - timedelta(days=i)).replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start_dt + timedelta(days=1)
        row = db.query(
            func.count(Order.id),
            func.coalesce(func.sum(Order.total), 0),
        ).filter(Order.created_at >= day_start_dt, Order.created_at < day_end).first()
        daily.append({"date": day, "orders": row[0], "revenue": round(row[1], 2)})

    recent = db.query(Order).order_by(Order.created_at.desc()).limit(10).all()

    return {
        "totalOrders": total_orders,
        "totalRevenue": round(total_revenue, 2),
        "totalUsers": total_users,
        "totalProducts": total_products,
        "pendingOrders": pending_orders,
        "todayRevenue": round(today_revenue, 2),
        "weekRevenue": round(week_revenue, 2),
        "monthlyRevenue": round(month_revenue, 2),
        "yearRevenue": round(year_revenue, 2),
        "todayOrders": today_orders,
        "ordersThisMonth": orders_this_month,
        "completedOrders": completed_orders,
        "newUsers": new_users_30,
        "activeUsers": active_users,
        "conversionRate": conversion_rate,
        "cartAbandonmentRate": round(100 - conversion_rate, 2),
        "averageOrderValue": round(avg_order, 2),
        "daily": daily,
        "recentOrders": [row_to_dict(o) for o in recent],
        "topProducts": [
            {"id": p.id, "name": p.name, "image": p.image, "price": p.price,
             "total_sold": p.total_sold, "total_revenue": round(p.total_revenue, 2)}
            for p in top_products
        ],
        "bottomProducts": [
            {"id": p.id, "name": p.name, "image": p.image, "price": p.price,
             "total_sold": p.total_sold}
            for p in bottom_products
        ],
    }


# ─── Orders Management ───────────────────────────────────────
@router.get("/orders")
async def admin_orders(admin=Depends(require_admin), db: Session = Depends(get_db)):
    results = db.query(Order, User).outerjoin(User, Order.user_id == User.id).order_by(
        Order.created_at.desc()
    ).limit(100).all()
    out = []
    for o, u in results:
        d = row_to_dict(o)
        d["user_name"] = u.name if u else "—"
        d["items"] = [row_to_dict(i) for i in o.items]
        out.append(d)
    return out


@router.get("/orders/{oid}")
async def admin_order_detail(oid: int, admin=Depends(require_admin), db: Session = Depends(get_db)):
    order = db.query(Order).filter(Order.id == oid).first()
    if not order:
        return {"error": "Orden no encontrada"}
    d = row_to_dict(order)
    d["items"] = [row_to_dict(i) for i in order.items]
    d["timeline"] = [row_to_dict(t) for t in order.timeline]
    d["user"] = row_to_dict(order.user) if order.user else None
    d["address"] = row_to_dict(order.address) if order.address else None
    return d


@router.post("/order/status")
async def admin_order_status(body: OrderStatusRequest,
                             admin=Depends(require_admin),
                             db: Session = Depends(get_db)):
    order = db.query(Order).filter(Order.id == body.id).first()
    if not order:
        return {"ok": False, "error": "Orden no encontrada"}
    order.status = body.status
    if body.status == "Entregado":
        order.delivered_at = datetime.now(timezone.utc)
    db.add(OrderTimeline(
        order_id=order.id, status=body.status,
        note=body.note or f"Estado actualizado: {body.status}",
        created_by=admin.name
    ))
    db.commit()
    return {"ok": True}


# ─── Products Management ─────────────────────────────────────
@router.get("/products")
async def admin_products(admin=Depends(require_admin), db: Session = Depends(get_db)):
    prods = db.query(Product).order_by(Product.id.desc()).all()
    result = []
    for p in prods:
        d = row_to_dict(p)
        d["variants"] = [row_to_dict(v) for v in p.variants]
        result.append(d)
    return result


@router.post("/products/{pid}/activate")
async def admin_activate_product(pid: int, admin=Depends(require_admin),
                                 db: Session = Depends(get_db)):
    p = db.query(Product).filter(Product.id == pid).first()
    if not p:
        return {"ok": False, "error": "Producto no encontrado"}
    p.status = "active"
    p.is_active = True
    db.commit()
    return {"ok": True, "status": p.status}


# ─── Customers Management ────────────────────────────────────
@router.get("/customers")
async def admin_customers(admin=Depends(require_admin), db: Session = Depends(get_db)):
    users = db.query(User).order_by(User.created_at.desc()).all()
    result = []
    for u in users:
        total_orders = db.query(func.count(Order.id)).filter(
            Order.user_id == u.id
        ).scalar() or 0
        total_spent = db.query(func.coalesce(func.sum(Order.total), 0)).filter(
            Order.user_id == u.id, Order.status != "Cancelado"
        ).scalar()
        last_order = db.query(Order).filter(Order.user_id == u.id).order_by(
            Order.created_at.desc()
        ).first()
        result.append({
            "id": u.id, "name": u.name, "email": u.email, "role": u.role,
            "phone": u.phone, "is_active": u.is_active,
            "email_verified": u.email_verified,
            "two_factor_enabled": u.two_factor_enabled,
            "total_orders": total_orders,
            "total_spent": round(total_spent, 2) if total_spent else 0,
            "last_order_date": last_order.created_at.isoformat() if last_order else None,
            "created_at": u.created_at.isoformat() if u.created_at else None,
        })
    return result


@router.post("/customers/{uid}/toggle-block")
async def toggle_customer_block(uid: int, admin=Depends(require_admin),
                                db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == uid).first()
    if not user or user.role == "admin":
        return {"ok": False, "error": "No puedes bloquear a este usuario"}
    user.is_active = not user.is_active
    db.commit()
    return {"ok": True, "is_active": user.is_active}


# ─── Categories Management ───────────────────────────────────
@router.get("/categories")
async def admin_categories(admin=Depends(require_admin), db: Session = Depends(get_db)):
    cats = db.query(Category).order_by(Category.sort_order).all()
    return [
        {
            "id": c.id, "name": c.name, "name_en": c.name_en, "slug": c.slug,
            "description": c.description, "image": c.image, "is_active": c.is_active,
            "sort_order": c.sort_order,
            "product_count": db.query(func.count(Product.id)).filter(
                Product.category_id == c.id
            ).scalar(),
        }
        for c in cats
    ]


@router.post("/categories")
async def admin_create_category(body: CategoryRequest, admin=Depends(require_admin),
                                db: Session = Depends(get_db)):
    cat = Category(**body.model_dump())
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return {"ok": True, "category": row_to_dict(cat)}


@router.put("/categories/{cid}")
async def admin_update_category(cid: int, body: dict, admin=Depends(require_admin),
                                db: Session = Depends(get_db)):
    cat = db.query(Category).filter(Category.id == cid).first()
    if not cat:
        return {"ok": False, "error": "Categoría no encontrada"}
    allowed = {"name", "name_en", "slug", "description", "image", "is_active", "sort_order"}
    for key, value in body.items():
        if key in allowed:
            setattr(cat, key, value)
    db.commit()
    return {"ok": True}


@router.delete("/categories/{cid}")
async def admin_delete_category(cid: int, admin=Depends(require_admin),
                                db: Session = Depends(get_db)):
    cat = db.query(Category).filter(Category.id == cid).first()
    if cat:
        db.delete(cat)
        db.commit()
    return {"ok": True}


# ─── Collections Management ──────────────────────────────────
@router.get("/collections")
async def admin_collections(admin=Depends(require_admin), db: Session = Depends(get_db)):
    cols = db.query(Collection).order_by(Collection.id.desc()).all()
    return [
        {**row_to_dict(c),
         "product_count": db.query(func.count(Product.id)).filter(
             Product.collection_id == c.id
         ).scalar()}
        for c in cols
    ]


@router.post("/collections")
async def admin_create_collection(body: CollectionRequest, admin=Depends(require_admin),
                                  db: Session = Depends(get_db)):
    col = Collection(**body.model_dump())
    db.add(col)
    db.commit()
    db.refresh(col)
    return {"ok": True, "collection": row_to_dict(col)}


@router.put("/collections/{cid}")
async def admin_update_collection(cid: int, body: dict, admin=Depends(require_admin),
                                  db: Session = Depends(get_db)):
    col = db.query(Collection).filter(Collection.id == cid).first()
    if not col:
        return {"ok": False, "error": "Colección no encontrada"}
    allowed = {"name", "name_en", "slug", "description", "image",
               "is_active", "is_featured", "start_date", "end_date"}
    for key, value in body.items():
        if key in allowed:
            setattr(col, key, value)
    db.commit()
    return {"ok": True}


@router.delete("/collections/{cid}")
async def admin_delete_collection(cid: int, admin=Depends(require_admin),
                                  db: Session = Depends(get_db)):
    col = db.query(Collection).filter(Collection.id == cid).first()
    if col:
        db.delete(col)
        db.commit()
    return {"ok": True}


@router.get("/collections/{cid}")
async def admin_collection_detail(cid: int, admin=Depends(require_admin),
                                  db: Session = Depends(get_db)):
    col = db.query(Collection).filter(Collection.id == cid).first()
    if not col:
        return {"error": "Colección no encontrada"}
    d = row_to_dict(col)
    d["products"] = [row_to_dict(p) for p in col.products]
    return d


# ─── Coupons Management ──────────────────────────────────────
@router.get("/coupons")
async def admin_coupons(admin=Depends(require_admin), db: Session = Depends(get_db)):
    return [row_to_dict(c) for c in db.query(Coupon).order_by(Coupon.id.desc()).all()]


@router.post("/coupons")
async def admin_create_coupon(body: dict, admin=Depends(require_admin),
                              db: Session = Depends(get_db)):
    coupon = Coupon(**{k: v for k, v in body.items() if hasattr(Coupon, k)})
    db.add(coupon)
    db.commit()
    db.refresh(coupon)
    return {"ok": True, "coupon": row_to_dict(coupon)}


@router.put("/coupons/{cid}")
async def admin_update_coupon(cid: int, body: dict, admin=Depends(require_admin),
                              db: Session = Depends(get_db)):
    coupon = db.query(Coupon).filter(Coupon.id == cid).first()
    if not coupon:
        return {"ok": False, "error": "Cupón no encontrado"}
    allowed = {"code", "description", "discount_type", "discount_value",
               "min_purchase", "max_discount", "usage_limit", "is_active", "expires_at"}
    for key, value in body.items():
        if key in allowed:
            setattr(coupon, key, value)
    db.commit()
    return {"ok": True}


@router.put("/coupons/{cid}/toggle")
async def admin_toggle_coupon(cid: int, admin=Depends(require_admin),
                              db: Session = Depends(get_db)):
    coupon = db.query(Coupon).filter(Coupon.id == cid).first()
    if not coupon:
        return {"ok": False, "error": "Cupón no encontrado"}
    coupon.is_active = not coupon.is_active
    db.commit()
    return {"ok": True, "is_active": coupon.is_active}


@router.delete("/coupons/{cid}")
async def admin_delete_coupon(cid: int, admin=Depends(require_admin),
                              db: Session = Depends(get_db)):
    coupon = db.query(Coupon).filter(Coupon.id == cid).first()
    if coupon:
        db.delete(coupon)
        db.commit()
    return {"ok": True}


# ─── Banners Management ──────────────────────────────────────
@router.get("/banners")
async def admin_banners(admin=Depends(require_admin), db: Session = Depends(get_db)):
    return [row_to_dict(b) for b in db.query(Banner).order_by(Banner.sort_order).all()]


@router.post("/banners")
async def admin_create_banner(body: dict, admin=Depends(require_admin),
                              db: Session = Depends(get_db)):
    banner = Banner(**{k: v for k, v in body.items() if hasattr(Banner, k)})
    db.add(banner)
    db.commit()
    db.refresh(banner)
    return {"ok": True, "banner": row_to_dict(banner)}


@router.delete("/banners/{bid}")
async def admin_delete_banner(bid: int, admin=Depends(require_admin),
                              db: Session = Depends(get_db)):
    banner = db.query(Banner).filter(Banner.id == bid).first()
    if banner:
        db.delete(banner)
        db.commit()
    return {"ok": True}


# ─── Newsletter Subscribers ──────────────────────────────────
@router.get("/newsletter-subscribers")
async def admin_newsletter(admin=Depends(require_admin), db: Session = Depends(get_db)):
    return [
        {
            "id": s.id, "email": s.email, "is_active": s.is_active,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        }
        for s in db.query(NewsletterSubscriber).order_by(
            NewsletterSubscriber.created_at.desc()
        ).all()
    ]


# ─── Activity Log ────────────────────────────────────────────
@router.get("/activity-log")
async def admin_activity_log(admin=Depends(require_admin), db: Session = Depends(get_db)):
    logs = db.query(ActivityLog).order_by(ActivityLog.created_at.desc()).limit(100).all()
    return [
        {
            "id": l.id, "user_id": l.user_id, "action": l.action,
            "entity_type": l.entity_type, "details": l.details,
            "ip_address": l.ip_address,
            "created_at": l.created_at.isoformat() if l.created_at else None,
        }
        for l in logs
    ]


# ─── Reviews Management ──────────────────────────────────────
@router.get("/reviews")
async def admin_reviews(admin=Depends(require_admin), db: Session = Depends(get_db)):
    reviews = db.query(Review, User, Product).join(User, Review.user_id == User.id).join(
        Product, Review.product_id == Product.id
    ).order_by(Review.created_at.desc()).limit(100).all()
    return [
        {
            "id": r.id, "user_name": u.name, "product_name": p.name,
            "rating": r.rating, "title": r.title, "comment": r.comment,
            "is_approved": r.is_approved, "is_reported": r.is_reported,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r, u, p in reviews
    ]


@router.post("/reviews/{rid}/toggle-approve")
async def admin_toggle_review(rid: int, admin=Depends(require_admin),
                              db: Session = Depends(get_db)):
    review = db.query(Review).filter(Review.id == rid).first()
    if review:
        review.is_approved = not review.is_approved
        db.commit()
    return {"ok": True}


# ─── Send Bulk Notification ──────────────────────────────────
@router.post("/notifications/send")
async def admin_send_notification(body: NotifSendRequest, admin=Depends(require_admin),
                                  db: Session = Depends(get_db)):
    users = db.query(User).filter(User.role == "client").all()
    for u in users:
        db.add(Notification(
            user_id=u.id, type=body.type, title=body.title, body=body.body
        ))
    db.commit()
    return {"ok": True}
