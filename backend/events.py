import socketio
from typing import Optional
from sqlalchemy.orm import Session
from database import SessionLocal
from models import Conversation, ChatMessage, User
from datetime import datetime, timezone

sio: Optional[socketio.AsyncServer] = None

active_admin_sids: set = set()


def init_socketio(server: socketio.AsyncServer):
    global sio
    sio = server

    @sio.event
    async def connect(sid, environ):
        pass

    @sio.event
    async def join_chat(sid, data):
        conversation_id = data.get("conversation_id")
        role = data.get("role", "user")
        user_id = data.get("user_id")
        if conversation_id:
            await sio.enter_room(sid, f"conversation_{conversation_id}")
        if role == "admin":
            active_admin_sids.add(sid)
            await sio.enter_room(sid, "admin_room")
        if user_id:
            await sio.enter_room(sid, f"user_{user_id}")

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



