import os
import time
from collections import defaultdict
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from database import get_db
from models import User, UserRole
from schemas import UserRegister, UserLogin, Token, UserOut
from auth import hash_password, verify_password, create_access_token, get_current_user, require_admin

router = APIRouter(prefix="/auth", tags=["Auth"])

# Simple in-memory rate limiter for login
_login_attempts: dict[str, list[float]] = defaultdict(list)
MAX_LOGIN_ATTEMPTS = int(os.getenv("RATE_LIMIT_LOGIN", "10"))
LOGIN_WINDOW = 60  # seconds

def check_login_rate_limit(ip: str):
    now = time.time()
    window_start = now - LOGIN_WINDOW
    _login_attempts[ip] = [t for t in _login_attempts[ip] if t > window_start]
    if len(_login_attempts[ip]) >= MAX_LOGIN_ATTEMPTS:
        raise HTTPException(status_code=429, detail="Demasiados intentos. Intentá de nuevo en un minuto.")
    _login_attempts[ip].append(now)


@router.post("/register")
def register(data: UserRegister, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == data.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email ya registrado")
    user = User(
        name=data.name,
        email=data.email,
        phone=data.phone,
        password_hash=hash_password(data.password),
        role=UserRole.client.value,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token({"sub": str(user.id)})
    return Token(
        access_token=token,
        token_type="bearer",
        user=UserOut(id=user.id, name=user.name, email=user.email, phone=user.phone, role=user.role)
    )


@router.post("/login")
def login(request: Request, data: UserLogin, db: Session = Depends(get_db)):
    client_ip = request.client.host if request.client else "unknown"
    check_login_rate_limit(client_ip)
    user = db.query(User).filter(User.email == data.email).first()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Credenciales inválidas")
    token = create_access_token({"sub": str(user.id)})
    return Token(
        access_token=token,
        token_type="bearer",
        user=UserOut(id=user.id, name=user.name, email=user.email, phone=user.phone, role=user.role)
    )


@router.get("/me")
def me(current_user: User = Depends(get_current_user)):
    return UserOut(id=current_user.id, name=current_user.name, email=current_user.email,
                   phone=current_user.phone, role=current_user.role)
