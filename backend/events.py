import socketio
from typing import Optional
from sqlalchemy.orm import Session
from database import SessionLocal
from models import Conversation, ChatMessage, User
from auth import SECRET_KEY, ALGORITHM
from jose import jwt, JWTError
from datetime import datetime, timezone

sio: Optional[socketio.AsyncServer] = None

active_admin_sids: set = set()


def _decode_user(token: str):
    """Devuelve (user_id, role) si el token es válido, o (None, None)."""
    if not token:
        return None, None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        uid = payload.get("sub")
        role = payload.get("role")
        return int(uid) if uid else None, role
    except (JWTError, ValueError, TypeError):
        return None, None


def init_socketio(server: socketio.AsyncServer):
    global sio
    sio = server

    @sio.event
    async def connect(sid, environ, auth):
        # auth llega del cliente (io(..., {auth: {token}}))
        token = (auth or {}).get("token", "") if isinstance(auth, dict) else ""
        uid, role = _decode_user(token)
        await sio.save_session(sid, {"user_id": uid, "role": role})
        return True

    @sio.event
    async def join_chat(sid, data):
        session = await sio.get_session(sid)
        uid = session.get("user_id")
        role = session.get("role")
        conversation_id = data.get("conversation_id")
        req_role = data.get("role", "user")
        req_user_id = data.get("user_id")
        guest_token = data.get("guest_token", "")

        # Solo admins autenticados pueden unirse a la sala de admin
        if req_role == "admin":
            is_admin = role == "admin"
            if not is_admin:
                db = SessionLocal()
                try:
                    u = db.query(User).filter(User.id == uid).first()
                    is_admin = bool(u and u.is_active and u.role == "admin")
                finally:
                    db.close()
            if not is_admin:
                return
            active_admin_sids.add(sid)
            await sio.enter_room(sid, "admin_room")
            return

        # Un usuario solo puede unirse a su propia sala
        if req_user_id:
            if role != "admin" and uid != int(req_user_id):
                return
            await sio.enter_room(sid, f"user_{req_user_id}")

        # Conversación: validar pertenencia o token de invitado
        if conversation_id:
            db = SessionLocal()
            try:
                conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
                if not conv:
                    return
                allowed = False
                if role == "admin":
                    allowed = True
                elif conv.user_id and uid == conv.user_id:
                    allowed = True
                elif not conv.user_id:
                    allowed = bool(guest_token) and conv.guest_token == guest_token
                if allowed:
                    await sio.enter_room(sid, f"conversation_{conversation_id}")
            finally:
                db.close()

    @sio.event
    async def leave_chat(sid, data):
        conversation_id = data.get("conversation_id")
        if conversation_id:
            await sio.leave_room(sid, f"conversation_{conversation_id}")

    @sio.event
    async def disconnect(sid):
        active_admin_sids.discard(sid)

    @sio.event
    async def typing(sid, data):
        conversation_id = data.get("conversation_id")
        is_admin = data.get("is_admin", False)
        sender_name = data.get("sender_name", "")
        if not conversation_id:
            return
        # Solo emiten typing quienes pueden ver la conversación:
        # admins autenticados o miembros de la sala de la conversación.
        rooms = await sio.rooms(sid)
        in_conv = f"conversation_{conversation_id}" in rooms
        if is_admin:
            if sid not in active_admin_sids and not in_conv:
                return
        elif not in_conv:
            return
        if is_admin:
            await sio.emit("user_typing", {
                "conversation_id": conversation_id,
                "is_admin": True,
                "sender_name": sender_name,
            }, room=f"conversation_{conversation_id}")
        else:
            await sio.emit("user_typing", {
                "conversation_id": conversation_id,
                "is_admin": False,
                "sender_name": sender_name,
            }, room="admin_room")


async def emit_new_message(conversation_id: int, message: dict):
    if sio:
        await sio.emit("new_message", message, room=f"conversation_{conversation_id}")
        if not message.get("is_admin"):
            await sio.emit("admin_new_message", {
                "conversation_id": conversation_id,
                "message": message,
            }, room="admin_room")
