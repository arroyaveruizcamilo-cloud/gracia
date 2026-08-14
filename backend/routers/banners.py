from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
from models import Banner, NewsletterSubscriber
from schemas import NewsletterRequest
from auth import get_current_user
from utils import db_to_dict as row_to_dict

router = APIRouter()


@router.get("/banners")
async def get_banners(db: Session = Depends(get_db)):
    return [row_to_dict(b) for b in db.query(Banner).filter(
        Banner.is_active == True
    ).order_by(Banner.sort_order).all()]


@router.post("/newsletter")
async def subscribe_newsletter(body: NewsletterRequest, db: Session = Depends(get_db)):
    existing = db.query(NewsletterSubscriber).filter(
        NewsletterSubscriber.email == body.email
    ).first()
    if existing:
        if not existing.is_active:
            existing.is_active = True
            db.commit()
        return {"ok": True, "message": "Ya estás suscrito"}
    db.add(NewsletterSubscriber(email=body.email))
    db.commit()
    return {"ok": True, "message": "Suscripción exitosa"}
