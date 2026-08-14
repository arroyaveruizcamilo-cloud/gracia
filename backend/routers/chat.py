from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import User, ChatMessage, Conversation
from schemas import ConversationCreate, ConversationOut, ChatMessageOut
from auth import get_current_user, require_admin
from events import emit_new_message
from datetime import datetime, timezone

router = APIRouter(prefix="/chat", tags=["Chat"])


def conv_to_dict(c: Conversation, db: Session) -> dict:
    last_msg = db.query(ChatMessage).filter(
        ChatMessage.conversation_id == c.id
    ).order_by(ChatMessage.created_at.desc()).first()
    return {
        "id": c.id,
        "user_id": c.user_id,
        "guest_name": c.guest_name,
        "guest_email": c.guest_email,
        "subject": c.subject,
        "status": c.status,
        "unread_count": c.unread_count,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
        "last_message": last_msg.message[:100] if last_msg else None,
    }


def msg_to_dict(m: ChatMessage, db: Session = None) -> dict:
    sender_name = ""
    if m.is_admin:
        if m.admin_id:
            admin_user = db.query(User).filter(User.id == m.admin_id).first() if db else None
            sender_name = admin_user.name if admin_user else "Admin"
        else:
            sender_name = "Admin"
    elif m.user_id:
        chat_user = db.query(User).filter(User.id == m.user_id).first() if db else None
        sender_name = chat_user.name if chat_user else "Cliente"
    else:
        conv = db.query(Conversation).filter(Conversation.id == m.conversation_id).first() if db else None
        sender_name = conv.guest_name if conv else "Cliente"
    return {
        "id": m.id,
        "conversation_id": m.conversation_id,
        "user_id": m.user_id,
        "is_admin": m.is_admin,
        "admin_id": m.admin_id,
        "message": m.message,
        "created_at": m.created_at.isoformat() if m.created_at else None,
        "read": m.read,
        "sender_name": sender_name,
    }


@router.post("/conversations")
def create_conversation(
    data: ConversationCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    conv = Conversation(
        user_id=user.id,
        guest_name=user.name,
        guest_email=user.email,
        subject=data.subject or "Consulta",
        status="active",
    )
    db.add(conv)
    db.flush()

    msg = ChatMessage(
        conversation_id=conv.id,
        user_id=user.id,
        message=data.message,
    )
    db.add(msg)
    db.commit()
    db.refresh(conv)

    return conv_to_dict(conv, db)


@router.post("/conversations/guest")
def create_guest_conversation(data: ConversationCreate, db: Session = Depends(get_db)):
    conv = Conversation(
        guest_name=data.guest_name or "Invitado",
        guest_email=data.guest_email or "",
        subject=data.subject or "Consulta",
        status="active",
    )
    db.add(conv)
    db.flush()

    msg = ChatMessage(
        conversation_id=conv.id,
        message=data.message,
    )
    db.add(msg)
    db.commit()
    db.refresh(conv)

    return conv_to_dict(conv, db)


@router.get("/conversations")
def get_user_conversations(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    convs = db.query(Conversation).filter(
        Conversation.user_id == user.id,
        Conversation.status == "active",
    ).order_by(Conversation.updated_at.desc()).all()
    return [conv_to_dict(c, db) for c in convs]


@router.get("/conversations/{conv_id}/messages")
def get_conversation_messages(
    conv_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    conv = db.query(Conversation).filter(Conversation.id == conv_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversación no encontrada")
    if conv.user_id and conv.user_id != user.id:
        raise HTTPException(status_code=403, detail="No autorizado")

    msgs = db.query(ChatMessage).filter(
        ChatMessage.conversation_id == conv_id
    ).order_by(ChatMessage.created_at).all()

    return [msg_to_dict(m, db) for m in msgs]


@router.post("/conversations/{conv_id}/messages")
async def send_message(
    conv_id: int,
    data: dict,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    conv = db.query(Conversation).filter(Conversation.id == conv_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversación no encontrada")
    if conv.user_id and conv.user_id != user.id:
        raise HTTPException(status_code=403, detail="No autorizado")

    msg = ChatMessage(
        conversation_id=conv_id,
        user_id=user.id,
        message=data.get("message", ""),
    )
    db.add(msg)
    conv.updated_at = datetime.now(timezone.utc)
    conv.unread_count = (conv.unread_count or 0) + 1
    db.commit()
    db.refresh(msg)

    msg_dict = msg_to_dict(msg, db)
    await emit_new_message(conv_id, msg_dict)
    return msg_dict


@router.post("/conversations/{conv_id}/read")
def mark_conversation_read(
    conv_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    conv = db.query(Conversation).filter(Conversation.id == conv_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversación no encontrada")
    if conv.user_id and conv.user_id != user.id:
        raise HTTPException(status_code=403, detail="No autorizado")

    conv.unread_count = 0
    db.query(ChatMessage).filter(
        ChatMessage.conversation_id == conv_id,
        ChatMessage.read == False,
    ).update({"read": True})
    db.commit()
    return {"ok": True}


# ===== ADMIN ENDPOINTS =====

@router.get("/admin/conversations")
def admin_list_conversations(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    convs = db.query(Conversation).filter(
        Conversation.status == "active"
    ).order_by(Conversation.updated_at.desc()).all()
    return [conv_to_dict(c, db) for c in convs]


@router.get("/admin/conversations/all")
def admin_list_all_conversations(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    convs = db.query(Conversation).order_by(
        Conversation.updated_at.desc()
    ).all()
    return [conv_to_dict(c, db) for c in convs]


@router.get("/admin/conversations/{conv_id}/messages")
def admin_get_messages(
    conv_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    conv = db.query(Conversation).filter(Conversation.id == conv_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversación no encontrada")

    msgs = db.query(ChatMessage).filter(
        ChatMessage.conversation_id == conv_id
    ).order_by(ChatMessage.created_at).all()

    return [msg_to_dict(m, db) for m in msgs]


@router.post("/admin/conversations/{conv_id}/reply")
async def admin_reply(
    conv_id: int,
    data: dict,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    conv = db.query(Conversation).filter(Conversation.id == conv_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversación no encontrada")

    msg = ChatMessage(
        conversation_id=conv_id,
        is_admin=True,
        admin_id=admin.id,
        message=data.get("message", ""),
        read=False,
    )
    db.add(msg)
    conv.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(msg)

    msg_dict = msg_to_dict(msg, db)
    await emit_new_message(conv_id, msg_dict)
    return msg_dict


@router.post("/admin/conversations/{conv_id}/close")
def admin_close_conversation(
    conv_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    conv = db.query(Conversation).filter(Conversation.id == conv_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversación no encontrada")
    conv.status = "closed"
    db.commit()
    return {"ok": True}


@router.post("/admin/conversations/{conv_id}/read")
def admin_mark_read(
    conv_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    db.query(ChatMessage).filter(
        ChatMessage.conversation_id == conv_id,
        ChatMessage.is_admin == False,
        ChatMessage.read == False,
    ).update({"read": True})
    db.commit()
    return {"ok": True}
