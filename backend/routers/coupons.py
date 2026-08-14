from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from database import get_db
from models import Coupon
from schemas import CouponCreate, CouponOut
from auth import require_admin

router = APIRouter(prefix="/coupons", tags=["Coupons"])


@router.get("")
def list_coupons(db: Session = Depends(get_db), admin=Depends(require_admin)):
    coupons = db.query(Coupon).all()
    return [CouponOut(
        id=c.id, code=c.code, discount_type=c.discount_type, discount_value=c.discount_value,
        min_purchase=c.min_purchase, usage_limit=c.usage_limit,
        used_count=c.used_count, is_active=c.is_active,
        expires_at=c.expires_at.isoformat() if c.expires_at else None,
    ) for c in coupons]


@router.post("")
def create_coupon(data: CouponCreate, db: Session = Depends(get_db), admin=Depends(require_admin)):
    existing = db.query(Coupon).filter(Coupon.code == data.code).first()
    if existing:
        raise HTTPException(status_code=400, detail="Código ya existe")
    c = Coupon(
        code=data.code.upper(), discount_type=data.discount_type, discount_value=data.discount_value,
        min_purchase=data.min_purchase, usage_limit=data.usage_limit,
        expires_at=datetime.fromisoformat(data.expires_at) if data.expires_at else None,
        is_active=True,
    )
    db.add(c)
    db.commit()
    return {"message": "Cupón creado"}


@router.put("/{coupon_id}/toggle")
def toggle_coupon(coupon_id: int, db: Session = Depends(get_db), admin=Depends(require_admin)):
    c = db.query(Coupon).filter(Coupon.id == coupon_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Cupón no encontrado")
    c.is_active = not c.is_active
    db.commit()
    return {"message": "Estado cambiado", "is_active": c.is_active}


@router.delete("/{coupon_id}")
def delete_coupon(coupon_id: int, db: Session = Depends(get_db), admin=Depends(require_admin)):
    c = db.query(Coupon).filter(Coupon.id == coupon_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Cupón no encontrado")
    db.delete(c)
    db.commit()
    return {"message": "Cupón eliminado"}


@router.post("/validate")
def validate_coupon(data: dict, db: Session = Depends(get_db)):
    code = data.get("code", "").upper()
    cart_total = data.get("cart_total", 0)
    c = db.query(Coupon).filter(Coupon.code == code, Coupon.is_active == True).first()
    if not c:
        raise HTTPException(status_code=404, detail="Cupón no válido")
    if c.usage_limit > 0 and c.used_count >= c.usage_limit:
        raise HTTPException(status_code=400, detail="Cupón agotado")
    if c.expires_at and c.expires_at < datetime.now():
        raise HTTPException(status_code=400, detail="Cupón expirado")
    if cart_total < c.min_purchase:
        raise HTTPException(status_code=400, detail=f"Compra mínima: ${c.min_purchase:.2f}")

    discount = (cart_total * c.discount_value / 100) if c.discount_type == "percentage" else c.discount_value
    if c.max_discount and discount > c.max_discount:
        discount = c.max_discount
    if discount > cart_total:
        discount = cart_total

    return {
        "valid": True,
        "code": c.code,
        "discount_type": c.discount_type,
        "discount_value": c.discount_value,
        "discount": round(discount, 2),
        "total_after": round(cart_total - discount, 2),
    }
