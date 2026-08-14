from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from database import get_db
from models import Product, ProductVariant, ProductImage
from schemas import ProductCreate, VariantCreate
from auth import require_admin

router = APIRouter(prefix="/products", tags=["Products"])


def product_to_dict(p):
    return {
        "id": p.id,
        "name": p.name,
        "description": p.description,
        "price": p.price,
        "old_price": p.old_price,
        "category": p.category,
        "stock": p.stock,
        "image": p.image,
        "status": p.status,
        "featured": p.featured,
        "variants": [
            {
                "id": v.id, "size": v.size, "color": v.color,
                "color_hex": v.color_hex, "sku": v.sku,
                "stock": v.stock, "price_override": v.price_override,
                "image": v.image,
            }
            for v in p.variants
        ],
        "images": [img.url for img in sorted(p.images, key=lambda x: x.sort_order)],
    }


@router.get("")
def list_products(
    category: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    featured: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
):
    q = db.query(Product).filter(Product.status == "active")
    if category:
        q = q.filter(Product.category == category)
    if search:
        q = q.filter(Product.name.ilike(f"%{search}%"))
    if featured is not None:
        q = q.filter(Product.featured == featured)
    products = q.all()
    return [product_to_dict(p) for p in products]


@router.get("/{product_id}")
def get_product(product_id: int, db: Session = Depends(get_db)):
    p = db.query(Product).filter(Product.id == product_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    return product_to_dict(p)


@router.post("")
def create_product(data: ProductCreate, db: Session = Depends(get_db), admin=Depends(require_admin)):
    p = Product(
        name=data.name, description=data.description, price=data.price,
        old_price=data.old_price, category=data.category, stock=data.stock,
        image=data.image, featured=data.featured,
    )
    db.add(p)
    db.flush()

    for v_data in data.variants:
        v = ProductVariant(product_id=p.id, **v_data.model_dump())
        db.add(v)

    for idx, img_url in enumerate(data.images):
        img = ProductImage(product_id=p.id, url=img_url, sort_order=idx)
        db.add(img)

    db.commit()
    db.refresh(p)
    return {"message": "Producto creado", "id": p.id}


@router.put("/{product_id}")
def update_product(product_id: int, data: ProductCreate, db: Session = Depends(get_db), admin=Depends(require_admin)):
    p = db.query(Product).filter(Product.id == product_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    for key in ("name", "description", "price", "old_price", "category", "stock", "image", "featured"):
        setattr(p, key, getattr(data, key))

    # Update variants
    db.query(ProductVariant).filter(ProductVariant.product_id == product_id).delete()
    for v_data in data.variants:
        v = ProductVariant(product_id=product_id, **v_data.model_dump())
        db.add(v)

    # Update images
    db.query(ProductImage).filter(ProductImage.product_id == product_id).delete()
    for idx, img_url in enumerate(data.images):
        img = ProductImage(product_id=product_id, url=img_url, sort_order=idx)
        db.add(img)

    db.commit()
    return {"message": "Producto actualizado"}


@router.delete("/{product_id}")
def delete_product(product_id: int, db: Session = Depends(get_db), admin=Depends(require_admin)):
    p = db.query(Product).filter(Product.id == product_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    p.status = "inactive"
    db.commit()
    return {"message": "Producto desactivado"}
