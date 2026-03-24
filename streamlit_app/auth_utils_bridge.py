"""
auth_utils_bridge.py - Thin wrappers that call the backend auth utilities
from Streamlit pages, keeping the pages clean of sys.path manipulation.
"""

import sys, os

# streamlit_app/ and server/ are siblings under the project root
STREAMLIT_APP_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT      = os.path.dirname(STREAMLIT_APP_DIR)
SERVER_DIR        = os.path.join(PROJECT_ROOT, "server")

for path in [SERVER_DIR, STREAMLIT_APP_DIR]:
    if path not in sys.path:
        sys.path.insert(0, path)

from auth.utils import verify_password, hash_password, validate_password_strength
from db import fetchone, execute


def change_password_action(user_id: int, current_pw: str, new_pw: str) -> tuple[bool, str]:
    """Validate and update a user's password."""
    user = fetchone("SELECT password_hash FROM users WHERE id=?", (user_id,))
    if not user or not verify_password(current_pw, user["password_hash"]):
        return False, "Current password is incorrect."

    valid, msg = validate_password_strength(new_pw)
    if not valid:
        return False, msg

    if verify_password(new_pw, user["password_hash"]):
        return False, "New password must differ from current password."

    execute(
        "UPDATE users SET password_hash=?, password_changed_at=datetime('now'), "
        "must_change_password=0 WHERE id=?",
        (hash_password(new_pw), user_id)
    )
    return True, "Password changed successfully."