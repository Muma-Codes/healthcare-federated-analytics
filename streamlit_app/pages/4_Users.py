"""
User management for admins.
Accessible to: admin only.
"""

import sys, os
import streamlit as st
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import render_sidebar
from auth_ui import require_role, current_user
from db   import fetchall, execute, fetchone

st.set_page_config(page_title="Users · Healthcare Analytics", page_icon="👥", layout="wide")
require_role("admin")
user = current_user()
render_sidebar()

st.title("User Management")
st.divider()

# Pending approvals banner
pending = fetchall("SELECT * FROM users WHERE role='pending' ORDER BY created_at DESC")
if pending:
    st.warning(f"⚠️ **{len(pending)} account(s) pending approval** — assign a role below to approve them.")

# Filter tabs
tab_all, tab_pending, tab_locked = st.tabs(["All Users", "Pending", "Locked"])

def _users_table(users: list):
    if not users:
        st.info("No users found.")
        return
    df = pd.DataFrame(users)[[
        "id","username","full_name","email","role",
        "is_active","is_approved","is_locked","last_login","created_at"
    ]]
    df["is_active"] = df["is_active"].map({1:"✅",0:"❌"})
    df["is_approved"] = df["is_approved"].map({1:"✅",0:"⏳"})
    df["is_locked"] = df["is_locked"].map({1:"🔒",0:"—"})
    st.dataframe(df, use_container_width=True, hide_index=True)

with tab_all:
    all_users = fetchall("SELECT * FROM users ORDER BY created_at DESC")
    _users_table(all_users)

with tab_pending:
    _users_table(pending)

with tab_locked:
    locked = fetchall("SELECT * FROM users WHERE is_locked=1")
    _users_table(locked)

st.divider()

# Actions
st.subheader("⚙️ Actions")

all_users_list = fetchall("SELECT id, username, role FROM users ORDER BY username")
user_options = {f"{u['username']} (id:{u['id']}, role:{u['role']})": u["id"] for u in all_users_list}

col1, col2 = st.columns(2)

# Assign role
with col1:
    st.markdown("**Assign / Change Role**")
    with st.form("assign_role_form"):
        selected_label = st.selectbox("Select User", list(user_options.keys()), key="role_select")
        new_role = st.selectbox("New Role", ["admin", "doctor", "nurse"])
        role_submit = st.form_submit_button("Assign Role", type="primary")

    if role_submit:
        target_id = user_options[selected_label]
        execute(
            "UPDATE users SET role=?, is_approved=1, is_active=1 WHERE id=?",
            (new_role, target_id)
        )
        execute(
            """INSERT INTO audit_logs (user_id, action, resource, detail, success, timestamp)
               VALUES (?,?,?,?,1,datetime('now'))""",
            (user["id"], "ROLE_UPDATED", f"users/{target_id}",
             f"role → {new_role}; approved=True")
        )
        st.success(f"Role updated to **{new_role}** and account approved.")
        st.rerun()

# Unlock / Deactivate
with col2:
    st.markdown("**Unlock / Deactivate Account**")
    with st.form("unlock_form"):
        selected_label2 = st.selectbox("Select User", list(user_options.keys()), key="action_select")
        action = st.selectbox("Action", ["Unlock Account", "Deactivate Account", "Reactivate Account"])
        action_submit = st.form_submit_button("Apply Action", type="primary")

    if action_submit:
        target_id2 = user_options[selected_label2]
        if target_id2 == user["id"] and action == "Deactivate Account":
            st.error("You cannot deactivate your own account.")
        else:
            if action == "Unlock Account":
                execute(
                    "UPDATE users SET is_locked=0, failed_login_attempts=0, locked_until=NULL WHERE id=?",
                    (target_id2,)
                )
                execute(
                    """INSERT INTO audit_logs (user_id, action, resource, success, timestamp)
                       VALUES (?,?,?,1,datetime('now'))""",
                    (user["id"], "USER_UNLOCKED", f"users/{target_id2}")
                )
                st.success("Account unlocked.")
            elif action == "Deactivate Account":
                execute("UPDATE users SET is_active=0 WHERE id=?", (target_id2,))
                execute(
                    """INSERT INTO audit_logs (user_id, action, resource, success, timestamp)
                       VALUES (?,?,?,1,datetime('now'))""",
                    (user["id"], "USER_DEACTIVATED", f"users/{target_id2}")
                )
                st.success("Account deactivated.")
            elif action == "Reactivate Account":
                execute("UPDATE users SET is_active=1 WHERE id=?", (target_id2,))
                st.success("Account reactivated.")
            st.rerun()