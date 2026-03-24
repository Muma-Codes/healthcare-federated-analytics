"""
Authentication endpoints
PUBLIC  (no token required):
  POST /auth/register          - anyone can create an account (role = "pending")
  POST /auth/login             - returns JWT or MFA challenge
  POST /auth/verify-mfa        - complete MFA second factor

PROTECTED (token required):
  POST /auth/logout            - invalidate current session
  POST /auth/change-password   - change own password
  GET  /auth/setup-mfa         - generate QR code for authenticator app
  POST /auth/confirm-mfa       - activate MFA after scanning QR
  GET  /auth/me                - current user profile

Registration flow:
  1. User fills in register form  ->  POST /auth/register
     Account is created with role = "pending", is_approved = False.
     User receives: "Your account is pending admin approval."
  2. Admin sees the pending user in GET /admin/users
  3. Admin calls PUT /admin/users/{id}/role  (assigns doctor | nurse | admin)
     is_approved is set to True automatically.
  4. User can now log in normally.
"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from auth.dependencies import get_current_user
from auth.utils import (
    create_access_token,
    decode_access_token,
    generate_qr_base64,
    generate_totp_secret,
    get_totp_uri,
    hash_password,
    hash_token,
    is_password_expired,
    validate_password_strength,
    verify_password,
    verify_totp,
)
from config import settings
from database.base import get_db
from database.models import AuditLog, User, UserSession
from notifications.email import send_alert_email

router = APIRouter(prefix="/auth", tags=["Authentication"])


# Request / Response Schemas

class SelfRegisterRequest(BaseModel):
    """Public self-registration. No role field - admin assigns it later."""
    username:  str
    email:     EmailStr
    full_name: str
    password:  str


class LoginRequest(BaseModel):
    username: str
    password: str


class MFAVerifyRequest(BaseModel):
    temp_token: str
    totp_code:  str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password:     str


class ConfirmMFARequest(BaseModel):
    totp_code: str


# Internal helpers

async def _log(
    db: AsyncSession, action: str, request: Request,
    user_id: int | None = None, resource: str | None = None,
    detail: str | None = None, success: bool = True,
):
    entry = AuditLog(
        user_id=user_id, action=action, resource=resource, detail=detail,
        ip_address=request.client.host if request.client else "unknown",
        user_agent=request.headers.get("user-agent", "")[:255],
        success=success,
    )
    db.add(entry)
    await db.flush()


async def _issue_full_token(user: User, db: AsyncSession, request: Request, ip: str) -> dict:
    token      = create_access_token({"sub": str(user.id), "role": user.role})
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    db.add(UserSession(user_id=user.id, token_hash=hash_token(token), expires_at=expires_at, ip_address=ip))
    await _log(db, "LOGIN_SUCCESS", request, user.id)
    return {
        "access_token": token,
        "token_type":   "bearer",
        "expires_in":   settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "user": {
            "id": user.id, "username": user.username, "full_name": user.full_name,
            "role": user.role, "is_approved": user.is_approved,
            "must_change_password": user.must_change_password,
            "password_expired": is_password_expired(user.password_changed_at),
            "mfa_enabled": user.mfa_enabled,
            "last_training_date": user.last_training_date.isoformat() if user.last_training_date else None,
        },
    }


# Endpoints

@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(payload: SelfRegisterRequest, request: Request, db: AsyncSession = Depends(get_db)):
    """
    Public self-registration — no authentication required.
    Account starts with role='pending' and is_approved=False.
    Login is blocked until an admin assigns a real role.
    """
    existing = await db.execute(
        select(User).where((User.username == payload.username) | (User.email == payload.email))
    )
    if existing.scalars().first():
        raise HTTPException(status_code=400, detail="Username or email is already taken.")

    valid, msg = validate_password_strength(payload.password)
    if not valid:
        raise HTTPException(status_code=400, detail=msg)

    user = User(
        username=payload.username, email=payload.email, full_name=payload.full_name,
        password_hash=hash_password(payload.password),
        role="pending", is_approved=False, must_change_password=False,
        password_changed_at=datetime.now(timezone.utc),
    )
    db.add(user)
    await db.flush()
    await _log(db, "REGISTER", request, user.id, f"users/{user.username}")

    await send_alert_email(
        subject=f"New account pending approval: {user.username}",
        body=(
            f"User '{user.full_name}' ({user.username}) has registered.\n"
            f"Email: {user.email}\n\nLog in as admin to assign their role."
        ),
    )

    return {
        "message": (
            "Account created successfully. "
            "Your account is pending administrator approval. "
            "You will be able to log in once an admin assigns your role."
        ),
        "username": user.username,
    }


@router.post("/login")
async def login(payload: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)):
    """
    Step 1 of login.
    Pending users get a clear 403 explaining they need approval.
    """
    ip = request.client.host if request.client else "unknown"
    result = await db.execute(select(User).where(User.username == payload.username))
    user: User | None = result.scalars().first()

    # Auto-unlock if lockout period has expired
    if user and user.is_locked:
        if user.locked_until and datetime.now(timezone.utc) < user.locked_until:
            await _log(db, "LOGIN_BLOCKED_LOCKED", request, user.id, success=False)
            raise HTTPException(status_code=403, detail="Account is locked. Contact your administrator.")
        user.is_locked = False
        user.failed_login_attempts = 0
        user.locked_until = None

    # Wrong credentials
    if not user or not verify_password(payload.password, user.password_hash):
        if user:
            user.failed_login_attempts += 1
            if user.failed_login_attempts >= settings.MAX_LOGIN_ATTEMPTS:
                user.is_locked    = True
                user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCOUNT_LOCKOUT_MINUTES)
                await send_alert_email(
                    subject=f"Account locked: {user.username}",
                    body=f"Locked after {settings.MAX_LOGIN_ATTEMPTS} failed attempts from {ip}.",
                )
        await _log(db, "LOGIN_FAIL", request, user.id if user else None, success=False)
        raise HTTPException(status_code=401, detail="Invalid username or password.")

    # Pending approval
    if not user.is_approved or user.role == "pending":
        await _log(db, "LOGIN_BLOCKED_PENDING", request, user.id, success=False)
        raise HTTPException(
            status_code=403,
            detail="Your account is pending administrator approval. Please check back later.",
        )

    if not user.is_active:
        raise HTTPException(status_code=403, detail="This account has been deactivated.")

    user.failed_login_attempts = 0
    user.last_login = datetime.now(timezone.utc)

    # MFA challenge
    if user.mfa_enabled and user.totp_secret:
        temp_token = create_access_token(
            {"sub": str(user.id), "stage": "pre_mfa"}, expires_delta=timedelta(minutes=5)
        )
        await _log(db, "LOGIN_STEP1_OK", request, user.id)
        return {"mfa_required": True, "temp_token": temp_token}

    return await _issue_full_token(user, db, request, ip)


@router.post("/verify-mfa")
async def verify_mfa(payload: MFAVerifyRequest, request: Request, db: AsyncSession = Depends(get_db)):
    """Step 2 — validate TOTP code and issue a full session token."""
    data = decode_access_token(payload.temp_token)
    if not data or data.get("stage") != "pre_mfa":
        raise HTTPException(status_code=401, detail="Invalid or expired pre-auth token.")
    result = await db.execute(select(User).where(User.id == int(data["sub"])))
    user: User | None = result.scalars().first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found.")
    if not verify_totp(user.totp_secret, payload.totp_code):
        await _log(db, "MFA_FAIL", request, user.id, success=False)
        raise HTTPException(status_code=401, detail="Invalid MFA code.")
    return await _issue_full_token(user, db, request, request.client.host if request.client else "unknown")


@router.post("/logout")
async def logout(request: Request, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    await db.execute(update(UserSession).where(UserSession.token_hash == hash_token(token)).values(is_active=False))
    await _log(db, "LOGOUT", request, current_user.id)
    return {"message": "Logged out successfully."}


@router.post("/change-password")
async def change_password(
    payload: ChangePasswordRequest, request: Request,
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user),
):
    if not verify_password(payload.current_password, current_user.password_hash):
        await _log(db, "PASSWORD_CHANGE_FAIL", request, current_user.id, success=False)
        raise HTTPException(status_code=400, detail="Current password is incorrect.")
    valid, msg = validate_password_strength(payload.new_password)
    if not valid:
        raise HTTPException(status_code=400, detail=msg)
    if verify_password(payload.new_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="New password must differ from current password.")
    current_user.password_hash        = hash_password(payload.new_password)
    current_user.password_changed_at  = datetime.now(timezone.utc)
    current_user.must_change_password = False
    await _log(db, "PASSWORD_CHANGED", request, current_user.id)
    return {"message": "Password changed successfully."}


@router.get("/setup-mfa")
async def setup_mfa(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    secret = generate_totp_secret()
    current_user.totp_secret = secret
    return {"qr_code": f"data:image/png;base64,{generate_qr_base64(get_totp_uri(secret, current_user.username))}", "secret": secret}


@router.post("/confirm-mfa")
async def confirm_mfa(
    payload: ConfirmMFARequest, request: Request,
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user),
):
    if not current_user.totp_secret:
        raise HTTPException(status_code=400, detail="Call GET /auth/setup-mfa first.")
    if not verify_totp(current_user.totp_secret, payload.totp_code):
        raise HTTPException(status_code=400, detail="Invalid TOTP code.")
    current_user.mfa_enabled = True
    await _log(db, "MFA_ENABLED", request, current_user.id)
    return {"message": "MFA enabled successfully."}


@router.get("/me")
async def me(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id, "username": current_user.username,
        "email": current_user.email, "full_name": current_user.full_name,
        "role": current_user.role, "is_approved": current_user.is_approved,
        "mfa_enabled": current_user.mfa_enabled,
        "must_change_password": current_user.must_change_password,
        "password_expired": is_password_expired(current_user.password_changed_at),
        "last_login": current_user.last_login.isoformat() if current_user.last_login else None,
        "last_training_date": current_user.last_training_date.isoformat() if current_user.last_training_date else None,
        "created_at": current_user.created_at.isoformat(),
    }