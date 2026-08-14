from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import User, Address, CartItem, Wishlist, Product, ProductVariant, Notification
from schemas import AddressCreate, AddressOut, CartItemCreate, CartItemOut, WishlistOut, NotificationOut
from auth import get_current_user

router = APIRouter(prefix="/users", tags=["Users"])


# ===== PROFILE =====
@router.get("/profile")
def get_profile(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "name": current_user.name,
        "email": current_user.email,
        "phone": current_user.phone,
        "role": current_user.role,
    }


@router.put("/profile")
def update_profile(data: dict, db: Session = Depends(get_db),
                   current_user: User = Depends(get_current_user)):
    user = db.query(User).filter(User.id == current_user.id).first()
    if "name" in data: user.name = data["name"]
    if "phone" in data: user.phone = data["phone"]
    db.commit()
    return {"message": "Perfil actualizado"}


# ===== ADDRESSES =====
@router.get("/addresses")
def list_addresses(db: Session = Depends(get_db),
                   current_user: User = Depends(get_current_user)):
    addrs = db.query(Address).filter(Address.user_id == current_user.id).all()
    return [AddressOut(id=a.id, name=a.name, phone=a.phone, street=a.street,
                       city=a.city, state=a.state, zip_code=a.zip_code,
                       is_default=a.is_default) for a in addrs]


@router.post("/addresses")
def create_address(data: AddressCreate, db: Session = Depends(get_db),
                   current_user: User = Depends(get_current_user)):
    if data.is_default:
        db.query(Address).filter(Address.user_id == current_user.id).update({"is_default": False})
    addr = Address(user_id=current_user.id, **data.model_dump())
    db.add(addr)
    db.commit()
    db.refresh(addr)
    return AddressOut(id=addr.id, name=addr.name, phone=addr.phone,
                      street=addr.street, city=addr.city, state=addr.state,
                      zip_code=addr.zip_code, is_default=addr.is_default)


@router.delete("/addresses/{addr_id}")
def delete_address(addr_id: int, db: Session = Depends(get_db),
                   current_user: User = Depends(get_current_user)):
    addr = db.query(Address).filter(Address.id == addr_id,
                                    Address.user_id == current_user.id).first()
    if not addr:
        raise HTTPException(status_code=404, detail="Dirección no encontrada")
    db.delete(addr)
    db.commit()
    return {"message": "Dirección eliminada"}


# ===== CART =====
@router.get("/cart")
def get_cart(db: Session = Depends(get_db),
             current_user: User = Depends(get_current_user)):
    items = db.query(CartItem).filter(CartItem.user_id == current_user.id).all()
    result = []
    for ci in items:
        p = ci.product
        v = db.query(ProductVariant).filter(ProductVariant.id == ci.variant_id).first() if ci.variant_id else None
        result.append(CartItemOut(
            id=ci.id, product_id=ci.product_id, variant_id=ci.variant_id,
            quantity=ci.quantity, product_name=p.name if p else "",
            product_price=v.price_override if v and v.price_override else (p.price if p else 0),
            product_image=((v and v.image) or (p and p.image)) or "",
            variant_size=v.size if v else "",
            variant_color=v.color if v else "",
            stock=v.stock if v else (p.stock if p else 0),
        ))
    return result


@router.post("/cart")
def add_to_cart(data: CartItemCreate, db: Session = Depends(get_db),
                current_user: User = Depends(get_current_user)):
    existing = db.query(CartItem).filter(
        CartItem.user_id == current_user.id,
        CartItem.product_id == data.product_id,
        CartItem.variant_id == data.variant_id,
    ).first()
    if existing:
        existing.quantity += data.quantity
    else:
        existing = CartItem(user_id=current_user.id, **data.model_dump())
        db.add(existing)
    db.commit()
    return {"message": "Añadido al carrito"}


@router.put("/cart/{item_id}")
def update_cart_qty(item_id: int, data: dict, db: Session = Depends(get_db),
                    current_user: User = Depends(get_current_user)):
    item = db.query(CartItem).filter(CartItem.id == item_id,
                                     CartItem.user_id == current_user.id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item no encontrado")
    item.quantity = data.get("quantity", item.quantity)
    db.commit()
    return {"message": "Cantidad actualizada"}


@router.delete("/cart/{item_id}")
def remove_from_cart(item_id: int, db: Session = Depends(get_db),
                     current_user: User = Depends(get_current_user)):
    item = db.query(CartItem).filter(CartItem.id == item_id,
                                     CartItem.user_id == current_user.id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item no encontrado")
    db.delete(item)
    db.commit()
    return {"message": "Eliminado del carrito"}


@router.delete("/cart")
def clear_cart(db: Session = Depends(get_db),
               current_user: User = Depends(get_current_user)):
    db.query(CartItem).filter(CartItem.user_id == current_user.id).delete()
    db.commit()
    return {"message": "Carrito vaciado"}


# ===== WISHLIST =====
@router.get("/wishlist")
def get_wishlist(db: Session = Depends(get_db),
                 current_user: User = Depends(get_current_user)):
    items = db.query(Wishlist).filter(Wishlist.user_id == current_user.id).all()
    result = []
    for w in items:
        p = w.product
        result.append(WishlistOut(
            id=w.id, product_id=w.product_id,
            product_name=p.name if p else "",
            product_price=p.price if p else 0,
            product_image=p.image if p else "",
        ))
    return result


@router.post("/wishlist/{product_id}")
def add_to_wishlist(product_id: int, db: Session = Depends(get_db),
                    current_user: User = Depends(get_current_user)):
    existing = db.query(Wishlist).filter(
        Wishlist.user_id == current_user.id,
        Wishlist.product_id == product_id,
    ).first()
    if existing:
        return {"message": "Ya está en favoritos"}
    w = Wishlist(user_id=current_user.id, product_id=product_id)
    db.add(w)
    db.commit()
    return {"message": "Añadido a favoritos"}


@router.delete("/wishlist/{product_id}")
def remove_from_wishlist(product_id: int, db: Session = Depends(get_db),
                         current_user: User = Depends(get_current_user)):
    w = db.query(Wishlist).filter(
        Wishlist.user_id == current_user.id,
        Wishlist.product_id == product_id,
    ).first()
    if w:
        db.delete(w)
        db.commit()
    return {"message": "Eliminado de favoritos"}


# ===== NOTIFICATIONS =====
@router.get("/notifications")
def list_notifications(db: Session = Depends(get_db),
                       current_user: User = Depends(get_current_user)):
    notifs = db.query(Notification).filter(
        Notification.user_id == current_user.id
    ).order_by(Notification.created_at.desc()).limit(20).all()
    return [NotificationOut(id=n.id, type=n.type, title=n.title,
                            body=n.body, read=n.read,
                            created_at=n.created_at) for n in notifs]


@router.put("/notifications/{notif_id}/read")
def mark_read(notif_id: int, db: Session = Depends(get_db),
              current_user: User = Depends(get_current_user)):
    n = db.query(Notification).filter(
        Notification.id == notif_id,
        Notification.user_id == current_user.id,
    ).first()
    if n:
        n.read = True
        db.commit()
    return {"message": "Leída"}


@router.get("/orders")
def get_user_orders(db: Session = Depends(get_db),
                    current_user: User = Depends(get_current_user)):
    from models import Order
    orders = db.query(Order).filter(Order.user_id == current_user.id).order_by(Order.created_at.desc()).all()
    result = []
    for o in orders:
        result.append({
            "id": o.id,
            "total": o.total,
            "status": o.status.value if hasattr(o.status, "value") else o.status,
            "payment_status": o.payment_status.value if hasattr(o.payment_status, "value") else o.payment_status,
            "created_at": o.created_at.isoformat() if o.created_at else None,
            "items": [{"product_name": i.product_name, "quantity": i.quantity, "price": i.price} for i in o.items],
        })
    return result
