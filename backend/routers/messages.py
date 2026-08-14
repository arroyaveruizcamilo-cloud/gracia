from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
from models import Message
from schemas import MessageCreate, MessageOut
from auth import require_admin

router = APIRouter(prefix="/messages", tags=["Messages"])


@router.post("")
def create_message(data: MessageCreate, db: Session = Depends(get_db)):
    m = Message(name=data.name, email=data.email, message=data.message)
    db.add(m)
    db.commit()
    db.refresh(m)
    return {"message": "Mensaje enviado", "id": m.id}


@router.get("")
def list_messages(db: Session = Depends(get_db), admin=Depends(require_admin)):
    msgs = db.query(Message).order_by(Message.created_at.desc()).all()
    return [
        {
            "id": m.id,
            "name": m.name,
            "email": m.email,
            "message": m.message,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in msgs
    ]
