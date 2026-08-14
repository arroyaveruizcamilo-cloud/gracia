from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import get_db
from models import User, Product, Review
from schemas import ReviewRequest
from auth import get_current_user
from utils import db_to_dict as row_to_dict

router = APIRouter()


def require_user(user: User | None = Depends(get_current_user)) -> User:
    from fastapi import HTTPException
    if not user:
        raise HTTPException(status_code=401, detail="Debes iniciar sesión")
    return user


@router.get("/reviews")
async def get_reviews(product_id: int = None, db: Session = Depends(get_db)):
    q = db.query(Review).filter(Review.is_approved == True)
    if product_id:
        q = q.filter(Review.product_id == product_id)
    reviews = q.order_by(Review.created_at.desc()).limit(50).all()
    result = []
    for r in reviews:
        d = row_to_dict(r)
        d["user_name"] = r.user.name if r.user else "Anónimo"
        result.append(d)
    return result


@router.get("/reviews/product/{pid}")
async def get_product_reviews(pid: int, db: Session = Depends(get_db)):
    reviews = db.query(Review, User).join(User, Review.user_id == User.id).filter(
        Review.product_id == pid, Review.is_approved == True
    ).order_by(Review.created_at.desc()).all()
    result = []
    for r, u in reviews:
        result.append({
            "id": r.id, "product_id": r.product_id, "user_id": r.user_id,
            "user_name": u.name, "rating": r.rating, "title": r.title,
            "comment": r.comment, "images": r.images,
            "helpful_count": r.helpful_count,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        })
    avg = db.query(func.avg(Review.rating)).filter(
        Review.product_id == pid, Review.is_approved == True
    ).scalar()
    total = db.query(func.count(Review.id)).filter(
        Review.product_id == pid, Review.is_approved == True
    ).scalar()
    distribution = {}
    for i in range(1, 6):
        distribution[str(i)] = db.query(func.count(Review.id)).filter(
            Review.product_id == pid, Review.rating == i, Review.is_approved == True
        ).scalar() or 0
    return {
        "reviews": result,
        "average": round(avg, 1) if avg else 0,
        "total": total or 0,
        "distribution": distribution,
    }


@router.post("/reviews")
async def create_review(body: ReviewRequest, user: User = Depends(require_user),
                        db: Session = Depends(get_db)):
    existing = db.query(Review).filter(
        Review.product_id == body.product_id,
        Review.user_id == user.id,
    ).first()
    if existing:
        return {"ok": False, "error": "Ya calificaste este producto"}

    product = db.query(Product).filter(Product.id == body.product_id).first()
    if not product:
        return {"ok": False, "error": "Producto no encontrado"}

    review = Review(
        product_id=body.product_id, user_id=user.id,
        order_item_id=body.order_item_id,
        rating=body.rating, title=body.title,
        comment=body.comment, images=body.images,
        is_approved=True,
    )
    db.add(review)
    db.commit()
    return {"ok": True, "review": row_to_dict(review)}


@router.put("/reviews/{rid}")
async def update_review(rid: int, body: ReviewRequest, user: User = Depends(require_user),
                        db: Session = Depends(get_db)):
    review = db.query(Review).filter(Review.id == rid, Review.user_id == user.id).first()
    if not review:
        return {"ok": False, "error": "Reseña no encontrada"}
    review.rating = body.rating
    review.title = body.title
    review.comment = body.comment
    review.images = body.images
    db.commit()
    return {"ok": True}


@router.delete("/reviews/{rid}")
async def delete_review(rid: int, user: User = Depends(require_user),
                        db: Session = Depends(get_db)):
    review = db.query(Review).filter(Review.id == rid, Review.user_id == user.id).first()
    if review:
        db.delete(review)
        db.commit()
    return {"ok": True}


@router.post("/reviews/{rid}/report")
async def report_review(rid: int, user: User = Depends(get_current_user),
                        db: Session = Depends(get_db)):
    review = db.query(Review).filter(Review.id == rid).first()
    if review:
        review.is_reported = True
        db.commit()
    return {"ok": True}


@router.post("/reviews/{rid}/helpful")
async def mark_helpful(rid: int, db: Session = Depends(get_db)):
    review = db.query(Review).filter(Review.id == rid).first()
    if review:
        review.helpful_count = (review.helpful_count or 0) + 1
        db.commit()
    return {"ok": True}
