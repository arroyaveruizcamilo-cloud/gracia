import os
import time
import logging
import secrets
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from database import get_db
from models import User, UserRole, ActivityLog
from schemas import (
    UserRegister, UserLogin, Token, UserOut,
    TwoFactorSetup, TwoFactorVerify, TwoFactorLoginRequest,
)
from auth import hash_password, verify_password, create_access_token, get_current_user, require_admin, SECRET_KEY, ALGORITHM
from services.email_service import send_password_reset
from pydantic import BaseModel, EmailStr
from jose import jwt

try:
    import pyotp
except ImportError:
    pyotp = None

router = APIRouter(prefix="/auth", tags=["Auth"])
logger = logging.getLogger("gracia.auth")

# --- Config ---
MAX_FAILED_ATTEMPTS = int(os.getenv("MAX_FAILED_ATTEMPTS", "5"))
LOCKOUT_MINUTES = int(os.getenv("LOCKOUT_MINUTES", "30"))
RESET_TOKEN_EXPIRE_MINUTES = 60

# In-memory login rate limiter (IP-based)
_login_attempts: dict[str, list[float]] = defaultdict(list)
MAX_LOGIN_ATTEMPTS = int(os.getenv("RATE_LIMIT_LOGIN", "10"))
LOGIN_WINDOW = 60

# Temporary tokens for 2FA flow (not yet verified)
_pending_2fa: dict[str, dict] = {}


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


def create_reset_token(user_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=RESET_TOKEN_EXPIRE_MINUTES)
    return jwt.encode(
        {"sub": str(user_id), "type": "password_reset", "exp": expire},
        SECRET_KEY, algorithm=ALGORITHM,
    )


def create_temp_2fa_token(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    _pending_2fa[token] = {
        "user_id": user_id,
        "expires": time.time() + 300,  # 5 minutes
    }
    return token


def cleanup_pending_2fa():
    now = time.time()
    expired = [k for k, v in _pending_2fa.items() if v["expires"] < now]
    for k in expired:
        del _pending_2fa[k]


def check_login_rate_limit(ip: str):
    now = time.time()
    window_start = now - LOGIN_WINDOW
    _login_attempts[ip] = [t for t in _login_attempts[ip] if t > window_start]
    if len(_login_attempts[ip]) >= MAX_LOGIN_ATTEMPTS:
        raise HTTPException(status_code=429, detail="Demasiados intentos. Intentá de nuevo en un minuto.")
    _login_attempts[ip].append(now)


def log_login_attempt(db: Session, user_id: int | None, email: str, ip: str, success: bool, reason: str = ""):
    entry = ActivityLog(
        user_id=user_id,
        action="login_success" if success else "login_failed",
        entity_type="auth",
        details=f"email={email} reason={reason}" if reason else f"email={email}",
        ip_address=ip,
    )
    db.add(entry)
    db.commit()
    level = logging.INFO if success else logging.WARNING
    logger.log(level, f"Login {'OK' if success else 'FAIL'} email={email} ip={ip} reason={reason}")


def check_account_lockout(user: User):
    if user.locked_until and user.locked_until > datetime.now(timezone.utc):
        remaining = (user.locked_until - datetime.now(timezone.utc)).seconds // 60 + 1
        raise HTTPException(
            status_code=423,
            detail=f"Cuenta bloqueada temporalmente. Intentá de nuevo en {remaining} minuto(s).",
        )
    if user.locked_until and user.locked_until <= datetime.now(timezone.utc):
        user.failed_login_attempts = 0
        user.locked_until = None


def handle_failed_login(user: User, db: Session):
    user.failed_login_attempts += 1
    if user.failed_login_attempts >= MAX_FAILED_ATTEMPTS:
        user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=LOCKOUT_MINUTES)
        logger.warning(f"Cuenta bloqueada: {user.email} por {LOCKOUT_MINUTES} min (intentos fallidos: {user.failed_login_attempts})")
    db.commit()


def reset_failed_logins(user: User, db: Session):
    if user.failed_login_attempts > 0 or user.locked_until:
        user.failed_login_attempts = 0
        user.locked_until = None
        db.commit()


# ===== REGISTER =====
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
    token = create_access_token({"sub": str(user.id), "role": user.role})
    return Token(
        access_token=token,
        token_type="bearer",
        user=UserOut(id=user.id, name=user.name, email=user.email, phone=user.phone, role=user.role),
    )


# ===== LOGIN =====
@router.post("/login")
def login(request: Request, data: UserLogin, db: Session = Depends(get_db)):
    client_ip = request.client.host if request.client else "unknown"
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        client_ip = forwarded.split(",")[0].strip()

    check_login_rate_limit(client_ip)

    user = db.query(User).filter(User.email == data.email).first()

    # Check lockout
    if user:
        check_account_lockout(user)

    # Validate credentials (use dummy hash if user not found to prevent timing attacks)
    dummy_hash = "$2b$12$LJ3m4ys3Lg.Ky8Y1k1xYzOeKzQ9KzQ9KzQ9KzQ9KzQ9KzQ9KzQ9"
    hash_to_check = user.password_hash if user else dummy_hash
    if not user or not verify_password(data.password, hash_to_check):
        if user:
            handle_failed_login(user, db)
            attempts_left = MAX_FAILED_ATTEMPTS - user.failed_login_attempts
            reason = f"credenciales_invalidas intentos_restantes={max(attempts_left, 0)}"
            log_login_attempt(db, user.id, data.email, client_ip, False, reason)
        else:
            log_login_attempt(db, None, data.email, client_ip, False, "usuario_no_existe")
        raise HTTPException(status_code=401, detail="Credenciales inválidas")

    if not user.is_active:
        log_login_attempt(db, user.id, data.email, client_ip, False, "cuenta_inactiva")
        raise HTTPException(status_code=403, detail="Tu cuenta está bloqueada. Contactá al administrador.")

    # Check if admin login is restricted to admin panel only
    # (clients can login via the same endpoint but won't get admin access)

    # Check 2FA
    if user.two_factor_enabled and user.two_factor_secret:
        temp_token = create_temp_2fa_token(user.id)
        log_login_attempt(db, user.id, data.email, client_ip, True, "2fa_requerido")
        return Token(
            access_token="",
            token_type="bearer",
            user=UserOut(id=user.id, name=user.name, email=user.email, phone=user.phone, role=user.role),
            requires_2fa=True,
        )

    # Success - no 2FA
    reset_failed_logins(user, db)
    user.last_login_at = datetime.now(timezone.utc)
    user.last_login_ip = client_ip
    db.commit()

    log_login_attempt(db, user.id, data.email, client_ip, True)
    token = create_access_token({"sub": str(user.id), "role": user.role})
    return Token(
        access_token=token,
        token_type="bearer",
        user=UserOut(id=user.id, name=user.name, email=user.email, phone=user.phone, role=user.role),
    )


# ===== 2FA VERIFY (during login) =====
@router.post("/2fa/verify")
def verify_2fa_login(request: Request, data: TwoFactorLoginRequest, db: Session = Depends(get_db)):
    client_ip = request.client.host if request.client else "unknown"

    cleanup_pending_2fa()
    pending = _pending_2fa.get(data.temp_token)
    if not pending or pending["expires"] < time.time():
        raise HTTPException(status_code=400, detail="Token de verificación expirado. Iniciá sesión de nuevo.")

    user = db.query(User).filter(User.id == pending["user_id"]).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Credenciales inválidas")

    if not pyotp:
        raise HTTPException(status_code=500, detail="2FA no disponible")

    totp = pyotp.TOTP(user.two_factor_secret)
    if not totp.verify(data.code, valid_window=1):
        handle_failed_login(user, db)
        log_login_attempt(db, user.id, user.email, client_ip, False, "2fa_codigo_invalido")
        raise HTTPException(status_code=401, detail="Código de verificación inválido")

    # 2FA verified - issue token
    del _pending_2fa[data.temp_token]
    reset_failed_logins(user, db)
    user.last_login_at = datetime.now(timezone.utc)
    user.last_login_ip = client_ip
    db.commit()

    log_login_attempt(db, user.id, user.email, client_ip, True)
    token = create_access_token({"sub": str(user.id), "role": user.role})
    return Token(
        access_token=token,
        token_type="bearer",
        user=UserOut(id=user.id, name=user.name, email=user.email, phone=user.phone, role=user.role),
    )


# ===== 2FA SETUP (admin only) =====
@router.post("/2fa/setup")
def setup_2fa(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    if not pyotp:
        raise HTTPException(status_code=500, detail="pyotp no instalado en el servidor")

    secret = pyotp.random_base32()
    totp = pyotp.TOTP(secret)
    provisioning_uri = totp.provisioning_uri(
        name=admin.email,
        issuer_name="Gracia Clothing Admin",
    )

    # Generate backup codes
    backup_codes = [secrets.token_hex(4) for _ in range(8)]

    # Store secret temporarily (not enabled yet - user must verify first)
    admin.two_factor_secret = secret
    db.commit()

    return TwoFactorSetup(
        secret=secret,
        qr_url=provisioning_uri,
        backup_codes=backup_codes,
    )


@router.post("/2fa/enable")
def enable_2fa(data: TwoFactorVerify, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    if not pyotp:
        raise HTTPException(status_code=500, detail="pyotp no instalado en el servidor")

    if not admin.two_factor_secret:
        raise HTTPException(status_code=400, detail="Primero debés configurar 2FA con /2fa/setup")

    totp = pyotp.TOTP(admin.two_factor_secret)
    if not totp.verify(data.code, valid_window=1):
        raise HTTPException(status_code=400, detail="Código inválido. Verificá en tu app de autenticación.")

    admin.two_factor_enabled = True
    db.commit()
    logger.info(f"2FA habilitado para admin: {admin.email}")
    return {"message": "Autenticación de dos factores habilitada correctamente"}


@router.post("/2fa/disable")
def disable_2fa(data: TwoFactorVerify, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    if not pyotp:
        raise HTTPException(status_code=500, detail="pyotp no instalado en el servidor")

    if not admin.two_factor_enabled:
        raise HTTPException(status_code=400, detail="2FA no está habilitado")

    totp = pyotp.TOTP(admin.two_factor_secret)
    if not totp.verify(data.code, valid_window=1):
        raise HTTPException(status_code=400, detail="Código inválido para deshabilitar 2FA")

    admin.two_factor_enabled = False
    admin.two_factor_secret = ""
    db.commit()
    logger.info(f"2FA deshabilitado para admin: {admin.email}")
    return {"message": "Autenticación de dos factores deshabilitada"}


# ===== ME =====
@router.get("/me")
def me(current_user: User = Depends(get_current_user)):
    return UserOut(id=current_user.id, name=current_user.name, email=current_user.email,
                   phone=current_user.phone, role=current_user.role)


# ===== FORGOT PASSWORD =====
@router.post("/forgot-password")
def forgot_password(data: ForgotPasswordRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email).first()
    if not user:
        return {"message": "Si el email existe, recibirás un enlace para restablecer tu contraseña"}
    token = create_reset_token(user.id)
    send_password_reset(user.email, token)
    return {"message": "Si el email existe, recibirás un enlace para restablecer tu contraseña"}


# ===== RESET PASSWORD =====
@router.post("/reset-password")
def reset_password(data: ResetPasswordRequest, db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(data.token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "password_reset":
            raise HTTPException(status_code=400, detail="Token inválido")
        user_id = int(payload.get("sub", 0))
        if not user_id:
            raise HTTPException(status_code=400, detail="Token inválido")
    except Exception:
        raise HTTPException(status_code=400, detail="El enlace es inválido o expiró. Solicitá uno nuevo.")

    if len(data.new_password) < 8:
        raise HTTPException(status_code=400, detail="La contraseña debe tener al menos 8 caracteres")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=400, detail="Usuario no encontrado")

    user.password_hash = hash_password(data.new_password)
    reset_failed_logins(user, db)
    db.commit()
    return {"message": "Contraseña actualizada. Ya podés iniciar sesión."}
