"""
Authentication helpers for the Streamlit frontend.

Reuses the existing backend auth utilities directly (password hashing,
JWT creation) so there is no duplication of logic.

Session state keys used throughout the app:
  st.session_state.logged_in  : bool
  st.session_state.user       : dict  (id, username, full_name, role, ...)
  st.session_state.token      : str   (JWT — stored for audit trail)
"""

import sys
import os

import streamlit as st

# Make the server package importable from the Streamlit app folder
SERVER_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "server")
if SERVER_DIR not in sys.path:
    sys.path.insert(0, SERVER_DIR)

from auth.utils import (
    hash_password,
    verify_password,
    create_access_token,
    validate_password_strength,
    is_password_expired,
)
from db import fetchone, execute


# Session helpers

def init_session():
    """Call once at the top of every page to initialise session keys."""
    for key, default in [
        ("logged_in", False),
        ("user", None),
        ("token", None),
    ]:
        if key not in st.session_state:
            st.session_state[key] = default


def is_logged_in() -> bool:
    return st.session_state.get("logged_in", False)


def current_user() -> dict | None:
    return st.session_state.get("user")


def require_login():
    """Redirect to login page if not authenticated. Called at the top of every protected page."""
    init_session()
    if not is_logged_in():
        st.warning("Please log in to access this page.")
        st.stop()


def require_role(*roles: str):
    """Stop page rendering if the current user's role is not in the allowed list."""
    require_login()
    user = current_user()
    if user and user.get("role") not in roles:
        st.error(f"Access denied. This page requires role: {', '.join(roles)}.")
        st.stop()


# Login

def login(username: str, password: str) -> tuple[bool, str]:
    """
    Verify credentials against the database.
    Returns (success, message).
    """
    user = fetchone(
        "SELECT * FROM users WHERE username = ?", (username,)
    )

    if not user:
        _increment_failed_attempts(username)
        return False, "Invalid username or password."

    # Locked account
    if user["is_locked"]:
        return False, "Account is locked. Contact your administrator."

    # Wrong password
    if not verify_password(password, user["password_hash"]):
        _increment_failed_attempts(username, user["id"])
        return False, "Invalid username or password."

    # Pending approval
    if not user["is_approved"] or user["role"] == "pending":
        return False, "Your account is pending administrator approval."

    # Inactive
    if not user["is_active"]:
        return False, "This account has been deactivated."

    # Success — write session
    token = create_access_token({"sub": str(user["id"]), "role": user["role"]})
    st.session_state.logged_in = True
    st.session_state.token     = token
    st.session_state.user      = {
        "id": user["id"],
        "username": user["username"],
        "email": user["email"],
        "full_name": user["full_name"],
        "role": user["role"],
        "mfa_enabled": bool(user["mfa_enabled"]),
        "must_change_password": bool(user["must_change_password"]),
        "last_login": user["last_login"],
        "last_training_date": user["last_training_date"],
    }

    # Reset failed attempts & update last_login
    execute(
        "UPDATE users SET failed_login_attempts=0, last_login=datetime('now') WHERE id=?",
        (user["id"],)
    )
    _write_audit(user["id"], "LOGIN_SUCCESS")
    return True, "Login successful."


def logout():
    _write_audit(st.session_state.user["id"] if st.session_state.user else None, "LOGOUT")
    st.session_state.logged_in = False
    st.session_state.user      = None
    st.session_state.token     = None
    st.rerun()


# Register

def register(username: str, email: str, full_name: str, password: str) -> tuple[bool, str]:
    """Self-registration - account starts as pending."""
    # Check duplicates
    existing = fetchone(
        "SELECT id FROM users WHERE username=? OR email=?", (username, email)
    )
    if existing:
        return False, "Username or email is already taken."

    valid, msg = validate_password_strength(password)
    if not valid:
        return False, msg

    execute(
        """INSERT INTO users
           (username, email, full_name, password_hash, role, is_approved,
            is_active, must_change_password, password_changed_at, created_at)
           VALUES (?,?,?,?,?,?,?,?,datetime('now'),datetime('now'))""",
        (username, email, full_name, hash_password(password),
         "pending", 0, 1, 0)
    )
    return True, "Account created! Awaiting administrator approval."


# Internal helpers

def _increment_failed_attempts(username: str, user_id: int | None = None):
    if user_id is None:
        row = fetchone("SELECT id, failed_login_attempts FROM users WHERE username=?", (username,))
        if not row:
            return
        user_id = row["id"]
        attempts = row["failed_login_attempts"] + 1
    else:
        row = fetchone("SELECT failed_login_attempts FROM users WHERE id=?", (user_id,))
        attempts = (row["failed_login_attempts"] if row else 0) + 1

    execute(
        "UPDATE users SET failed_login_attempts=? WHERE id=?",
        (attempts, user_id)
    )
    if attempts >= 5:
        execute("UPDATE users SET is_locked=1 WHERE id=?", (user_id,))
    _write_audit(user_id, "LOGIN_FAIL", success=0)


def _write_audit(user_id, action: str, detail: str = "", success: int = 1):
    try:
        execute(
            """INSERT INTO audit_logs (user_id, action, detail, success, timestamp)
               VALUES (?,?,?,?,datetime('now'))""",
            (user_id, action, detail, success)
        )
    except Exception:
        pass   # audit must never crash the app