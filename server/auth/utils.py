"""
Authentication utilities:
  - Password hashing / verification
  - JWT creation / decoding
  - TOTP (MFA) generation and verification
  - Column-level AES encryption for sensitive DB fields
  - Password-policy checks
"""

import base64
import hashlib
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

import pyotp
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from jose import JWTError, jwt
from passlib.context import CryptContext

from config import settings


# Password hashing
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# Password policy
PASSWORD_REGEX = re.compile(
    r"^(?=.*[A-Z])(?=.*[a-z])(?=.*\d)(?=.*[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>\/?]).{8,}$"
)


def validate_password_strength(password: str) -> tuple[bool, str]:
    """
    Returns (is_valid, error_message).
    Rules: ≥8 chars, uppercase, lowercase, digit, special char.
    """
    if len(password) < settings.PASSWORD_MIN_LENGTH:
        return False, f"Password must be at least {settings.PASSWORD_MIN_LENGTH} characters."
    if not PASSWORD_REGEX.match(password):
        return False, (
            "Password must contain at least one uppercase letter, "
            "one lowercase letter, one digit and one special character."
        )
    return True, ""


def is_password_expired(password_changed_at: Optional[datetime]) -> bool:
    if password_changed_at is None:
        return True  # Never changed -> treat as expired
    if password_changed_at.tzinfo is None:
        password_changed_at = password_changed_at.replace(tzinfo=timezone.utc)

    expiry = password_changed_at + timedelta(days=settings.PASSWORD_EXPIRY_DAYS)

    return datetime.now(timezone.utc) > expiry


# JWT

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return None


def hash_token(token: str) -> str:
    """SHA-256 hash of a JWT for safe storage in the sessions table."""
    return hashlib.sha256(token.encode()).hexdigest()


# MFA / TOTP

def generate_totp_secret() -> str:
    return pyotp.random_base32()


def get_totp_uri(secret: str, username: str) -> str:
    totp = pyotp.TOTP(secret)
    return totp.provisioning_uri(name=username, issuer_name=settings.APP_NAME)


def verify_totp(secret: str, code: str) -> bool:
    totp = pyotp.TOTP(secret)
    return totp.verify(code, valid_window=1)  # +-30 sec tolerance


def generate_qr_base64(uri: str) -> str:
    """Return a base64-encoded PNG of a QR code for the TOTP URI."""
    import io
    import qrcode

    qr = qrcode.make(uri)
    buf = io.BytesIO()
    qr.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


# AES-256 column encryption
# Used to encrypt prediction input_features JSON before storage.

def _get_aes_key() -> bytes:
    """Derive a 32-byte key from the configured ENCRYPTION_KEY string."""
    raw = settings.ENCRYPTION_KEY.encode()
    return hashlib.sha256(raw).digest()  # always 32 bytes


def encrypt_text(plaintext: str) -> str:
    """AES-256-GCM encrypt → base64 string (iv:tag:ciphertext)."""
    key = _get_aes_key()
    iv = os.urandom(12)
    encryptor = Cipher(
        algorithms.AES(key), modes.GCM(iv), backend=default_backend()
    ).encryptor()
    ct = encryptor.update(plaintext.encode()) + encryptor.finalize()
    tag = encryptor.tag
    combined = base64.b64encode(iv + tag + ct).decode()
    return combined


def decrypt_text(encrypted: str) -> str:
    """Reverse of encrypt_text."""
    key = _get_aes_key()
    raw = base64.b64decode(encrypted.encode())
    iv, tag, ct = raw[:12], raw[12:28], raw[28:]
    decryptor = Cipher(
        algorithms.AES(key), modes.GCM(iv, tag), backend=default_backend()
    ).decryptor()
    return (decryptor.update(ct) + decryptor.finalize()).decode()