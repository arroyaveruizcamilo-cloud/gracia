import os
import time
import logging
import secrets
import httpx
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
from services.email_service import send_password_reset, send_login_alert_admin, send_new_device_alert, send_account_locked_alert
from pydantic import BaseModel, EmailStr
from jose import jwt

try:
    import pyotp
except ImportError:
    pyotp = None

router = APIRouter(prefix="/auth", tags=["Auth"])
logger = logging.getLogger("gracia.auth")

# reCAPTCHA config
RECAPTCHA_SECRET_KEY = os.getenv("RECAPTCHA_SECRET_KEY", "")
RECAPTCHA_VERIFY_URL = "https://www.google.com/recaptcha/api/siteverify"
RECAPTCHA_MIN_SCORE = 0.5  # For v3; for v2, success field is used

# --- Config ---
MAX_FAILED_ATTEMPTS = int(os.getenv("MAX_FAILED_ATTEMPTS", "5"))
LOCKOUT_MINUTES = int(os.getenv("LOCKOUT_MINUTES", "30"))
RESET_TOKEN_EXPIRE_MINUTES = 60

# In-memory login rate limiter (IP-based)
_login_attempts: dict[str, list[float]] = defaultdict(list)


def _get_admin_email(db: Session) -> str:
    admin_email = os.getenv("SEED_ADMIN_EMAIL", "")
    if admin_email:
        return admin_email
    admin = db.query(User).filter(User.role == "admin").first()
    return admin.email if admin else ""


def _get_user_agent(request: Request) -> str:
    return request.headers.get("user-agent", "desconocido")[:120]


def _is_new_ip(user: User, current_ip: str) -> bool:
    return bool(user.last_login_ip and user.last_login_ip != current_ip)


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
    user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
    if user.failed_login_attempts >= MAX_FAILED_ATTEMPTS:
        user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=LOCKOUT_MINUTES)
        logger.warning(f"Cuenta bloqueada: {user.email} por {LOCKOUT_MINUTES} min (intentos fallidos: {user.failed_login_attempts})")
    db.commit()


def reset_failed_logins(user: User, db: Session):
    if (user.failed_login_attempts or 0) > 0 or user.locked_until:
        user.failed_login_attempts = 0
        user.locked_until = None
        db.commit()


async def verify_recaptcha(token: str, remote_ip: str = "") -> bool:
    """Verify a reCAPTCHA token with Google. Returns True if valid."""
    if not RECAPTCHA_SECRET_KEY:
        # reCAPTCHA not configured — skip verification (dev mode)
        return True
    if not token:
        return False
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(RECAPTCHA_VERIFY_URL, data={
                "secret": RECAPTCHA_SECRET_KEY,
                "response": token,
                "remoteip": remote_ip,
            })
            result = resp.json()
            return result.get("success", False)
    except Exception as e:
        logger.error(f"reCAPTCHA verification error: {e}")
        return False


# ===== MATH CAPTCHA (custom, no Google needed) =====
import random
import hashlib

_CAPTCHA_EXPIRE_SECONDS = 120  # 2 minutes

class CaptchaChallenge(BaseModel):
    question: str
    token: str

class CaptchaVerify(BaseModel):
    token: str
    answer: int


def _generate_captcha_token(a: int, b: int, op: str, answer: int) -> str:
    ts = int(time.time())
    payload = f"{a}:{op}:{b}:{answer}:{ts}"
    sig = hashlib.sha256((payload + ":" + SECRET_KEY).encode()).hexdigest()[:16]
    return f"{a}:{op}:{b}:{ts}:{sig}"


def _verify_captcha_token(token: str, user_answer: int) -> bool:
    try:
        parts = token.split(":")
        if len(parts) != 5:
            return False
        a, op, b, ts_str, sig = parts
        ts = int(ts_str)
        if time.time() - ts > _CAPTCHA_EXPIRE_SECONDS:
            return False
        if op == "+":
            correct = int(a) + int(b)
        elif op == "-":
            correct = int(a) - int(b)
        elif op == "*":
            correct = int(a) * int(b)
        else:
            return False
        if user_answer != correct:
            return False
        expected_sig = hashlib.sha256(f"{a}:{op}:{b}:{correct}:{ts}:{SECRET_KEY}".encode()).hexdigest()[:16]
        return sig == expected_sig
    except Exception:
        return False


@router.get("/captcha", response_model=CaptchaChallenge)
def generate_captcha():
    ops = ["+", "-", "*"]
    op = random.choice(ops)
    if op == "+":
        a, b = random.randint(1, 50), random.randint(1, 50)
    elif op == "-":
        a = random.randint(10, 60)
        b = random.randint(1, a)
    else:
        a, b = random.randint(2, 12), random.randint(2, 12)
    answer = eval(f"{a} {op} {b}")
    token = _generate_captcha_token(a, b, op, answer)
    question = f"¿Cuánto es {a} {op} {b}?"
    return CaptchaChallenge(question=question, token=token)


@router.post("/captcha/verify")
def verify_captcha(data: CaptchaVerify):
    if not _verify_captcha_token(data.token, data.answer):
        raise HTTPException(status_code=400, detail="CAPTCHA incorrecto. Intentá de nuevo.")
    return {"valid": True}


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
async def login(request: Request, data: UserLogin, db: Session = Depends(get_db)):
    client_ip = request.client.host if request.client else "unknown"
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        client_ip = forwarded.split(",")[0].strip()

    check_login_rate_limit(client_ip)

    # Verify reCAPTCHA token
    if RECAPTCHA_SECRET_KEY and not await verify_recaptcha(data.recaptcha_token, client_ip):
        log_login_attempt(db, None, data.email, client_ip, False, "recaptcha_failed")
        admin_email = _get_admin_email(db)
        if admin_email:
            try:
                send_login_alert_admin(admin_email, data.email, client_ip, _get_user_agent(request), False, "recaptcha_failed")
            except Exception:
                pass
        raise HTTPException(status_code=403, detail="Verificación reCAPTCHA fallida. Intentá de nuevo.")

    # Verify math CAPTCHA (only enforced for admin logins)
    user_check = db.query(User).filter(User.email == data.email).first()
    is_admin_login = user_check and user_check.role == UserRole.admin.value
    if is_admin_login:
        if data.captcha_token and not _verify_captcha_token(data.captcha_token, data.captcha_answer):
            log_login_attempt(db, user_check.id if user_check else None, data.email, client_ip, False, "captcha_failed")
            raise HTTPException(status_code=403, detail="CAPTCHA incorrecto. Intentá de nuevo.")
        elif not RECAPTCHA_SECRET_KEY and not data.captcha_token:
            log_login_attempt(db, user_check.id if user_check else None, data.email, client_ip, False, "captcha_missing")
            raise HTTPException(status_code=403, detail="Debes completar el CAPTCHA.")

    user = user_check

    # Check lockout
    if user:
        try:
            check_account_lockout(user)
        except HTTPException as e:
            if e.status_code == 423:
                admin_email = _get_admin_email(db)
                if admin_email:
                    try:
                        send_login_alert_admin(admin_email, data.email, client_ip, _get_user_agent(request), False, "cuenta_bloqueada")
                    except Exception:
                        pass
            raise

    # Validate credentials (use dummy hash if user not found to prevent timing attacks)
    dummy_hash = "$2b$12$LJ3m4ys3Lg.Ky8Y1k1xYzOeKzQ9KzQ9KzQ9KzQ9KzQ9KzQ9KzQ9"
    hash_to_check = user.password_hash if user else dummy_hash
    user_agent = _get_user_agent(request)
    admin_email = _get_admin_email(db)

    if not user or not verify_password(data.password, hash_to_check):
        if user:
            handle_failed_login(user, db)
            attempts_left = MAX_FAILED_ATTEMPTS - user.failed_login_attempts
            reason = f"credenciales_invalidas intentos_restantes={max(attempts_left, 0)}"
            log_login_attempt(db, user.id, data.email, client_ip, False, reason)
            # Notify admin of failed login attempt
            if admin_email:
                try:
                    send_login_alert_admin(admin_email, data.email, client_ip, user_agent, False, reason)
                except Exception:
                    pass
            # If account just got locked, notify the user
            if user.failed_login_attempts >= MAX_FAILED_ATTEMPTS and user.locked_until:
                if admin_email != user.email:
                    try:
                        send_account_locked_alert(user.email, user.name, client_ip, LOCKOUT_MINUTES)
                    except Exception:
                        pass
        else:
            log_login_attempt(db, None, data.email, client_ip, False, "usuario_no_existe")
            # Notify admin of attempt with non-existent email
            if admin_email:
                try:
                    send_login_alert_admin(admin_email, data.email, client_ip, user_agent, False, "usuario_no_existe")
                except Exception:
                    pass
        raise HTTPException(status_code=401, detail="Credenciales inválidas")

    if not user.is_active:
        log_login_attempt(db, user.id, data.email, client_ip, False, "cuenta_inactiva")
        if admin_email:
            try:
                send_login_alert_admin(admin_email, data.email, client_ip, user_agent, False, "cuenta_inactiva")
            except Exception:
                pass
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
            temp_token=temp_token,
        )

    # Success - no 2FA
    new_ip = _is_new_ip(user, client_ip)
    reset_failed_logins(user, db)
    user.last_login_at = datetime.now(timezone.utc)
    user.last_login_ip = client_ip
    db.commit()

    log_login_attempt(db, user.id, data.email, client_ip, True)
    token = create_access_token({"sub": str(user.id), "role": user.role})

    # Notify admin of successful login
    if admin_email:
        try:
            send_login_alert_admin(admin_email, data.email, client_ip, user_agent, True)
        except Exception:
            pass

    # Alert user if login from new IP/device
    if new_ip:
        try:
            send_new_device_alert(user.email, user.name, client_ip, user_agent)
        except Exception:
            pass

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
        user_agent = _get_user_agent(request)
        admin_email = _get_admin_email(db)
        if admin_email:
            try:
                send_login_alert_admin(admin_email, user.email, client_ip, user_agent, False, "2fa_codigo_invalido")
            except Exception:
                pass
        raise HTTPException(status_code=401, detail="Código de verificación inválido")

    # 2FA verified - issue token
    new_ip = _is_new_ip(user, client_ip)
    del _pending_2fa[data.temp_token]
    reset_failed_logins(user, db)
    user.last_login_at = datetime.now(timezone.utc)
    user.last_login_ip = client_ip
    db.commit()

    log_login_attempt(db, user.id, user.email, client_ip, True)
    token = create_access_token({"sub": str(user.id), "role": user.role})

    user_agent = _get_user_agent(request)
    admin_email = _get_admin_email(db)
    if admin_email:
        try:
            send_login_alert_admin(admin_email, user.email, client_ip, user_agent, True)
        except Exception:
            pass
    if new_ip:
        try:
            send_new_device_alert(user.email, user.name, client_ip, user_agent)
        except Exception:
            pass

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
