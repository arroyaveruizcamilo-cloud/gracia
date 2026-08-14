from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import FAQ
from schemas import FAQCreate, FAQOut
from auth import require_admin

router = APIRouter(prefix="/faqs", tags=["FAQs"])


@router.get("")
def list_faqs(db: Session = Depends(get_db)):
    faqs = db.query(FAQ).filter(FAQ.active == True).order_by(FAQ.sort_order).all()
    return [FAQOut(id=f.id, question=f.question, answer=f.answer,
                   category=f.category, sort_order=f.sort_order, active=f.active) for f in faqs]


@router.get("/all")
def list_all_faqs(db: Session = Depends(get_db), admin=Depends(require_admin)):
    faqs = db.query(FAQ).order_by(FAQ.sort_order).all()
    return [FAQOut(id=f.id, question=f.question, answer=f.answer,
                   category=f.category, sort_order=f.sort_order, active=f.active) for f in faqs]


@router.post("")
def create_faq(data: FAQCreate, db: Session = Depends(get_db), admin=Depends(require_admin)):
    f = FAQ(**data.model_dump())
    db.add(f)
    db.commit()
    return {"message": "FAQ creada"}


@router.put("/{faq_id}")
def update_faq(faq_id: int, data: FAQCreate, db: Session = Depends(get_db), admin=Depends(require_admin)):
    f = db.query(FAQ).filter(FAQ.id == faq_id).first()
    if not f:
        raise HTTPException(status_code=404, detail="FAQ no encontrada")
    for key, val in data.model_dump().items():
        setattr(f, key, val)
    db.commit()
    return {"message": "FAQ actualizada"}


@router.delete("/{faq_id}")
def delete_faq(faq_id: int, db: Session = Depends(get_db), admin=Depends(require_admin)):
    f = db.query(FAQ).filter(FAQ.id == faq_id).first()
    if not f:
        raise HTTPException(status_code=404, detail="FAQ no encontrada")
    db.delete(f)
    db.commit()
    return {"message": "FAQ eliminada"}


@router.put("/{faq_id}/toggle")
def toggle_faq(faq_id: int, db: Session = Depends(get_db), admin=Depends(require_admin)):
    f = db.query(FAQ).filter(FAQ.id == faq_id).first()
    if not f:
        raise HTTPException(status_code=404, detail="FAQ no encontrada")
    f.active = not f.active
    db.commit()
    return {"message": "Estado cambiado"}
