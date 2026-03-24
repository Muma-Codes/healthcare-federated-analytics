"""
View and update own account details.
Accessible to all authenticated roles.
"""

import sys, os
import streamlit as st
import pandas as pd
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import render_sidebar
from auth_ui import require_login, current_user
from db   import fetchone, execute, fetchall
from auth_utils_bridge import change_password_action

st.set_page_config(page_title="Profile · Healthcare Analytics", page_icon="👤", layout="wide")
require_login()
user = current_user()
render_sidebar()

st.title("My Profile")
st.divider()

# Profile details
db_user = fetchone("SELECT * FROM users WHERE id=?", (user["id"],))

col1, col2 = st.columns([1, 2])

with col1:
    st.markdown(
        f"""
        <div style='background:#2563EB; color:white; border-radius:50%;
                    width:90px; height:90px; display:flex; align-items:center;
                    justify-content:center; font-size:2.5rem; margin:auto;'>
            {user['full_name'][0].upper()}
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(f"<p style='text-align:center; margin-top:8px;'><b>{user['full_name']}</b></p>", unsafe_allow_html=True)

with col2:
    r1, r2 = st.columns(2)
    r1.markdown(f"**Username**  \n`{db_user['username']}`")
    r2.markdown(f"**Email**  \n`{db_user['email']}`")
    r1.markdown(f"**Role**  \n`{db_user['role'].capitalize()}`")
    r2.markdown(f"**Account Status**  \n`{'✅ Active' if db_user['is_active'] else '❌ Inactive'}`")
    r1.markdown(f"**MFA Enabled**  \n`{'Yes 🔐' if db_user['mfa_enabled'] else 'No'}`")
    last_login = db_user['last_login'] or "Never"
    r2.markdown(f"**Last Login**  \n`{last_login}`")
    last_training = db_user['last_training_date'] or "Never"
    r1.markdown(f"**Last Security Training**  \n`{last_training}`")
    r2.markdown(f"**Member Since**  \n`{db_user['created_at'][:10]}`")

st.divider()

# Change password
st.subheader("Change Password")
with st.form("change_pw_form"):
    current_pw = st.text_input("Current Password", type="password")
    new_pw = st.text_input("New Password", type="password", help=">=8 chars, uppercase, lowercase, digit, special character")
    confirm_pw = st.text_input("Confirm New Password", type="password")
    pw_submit = st.form_submit_button("Update Password", type="primary")

if pw_submit:
    if not current_pw or not new_pw or not confirm_pw:
        st.error("All password fields are required.")
    elif new_pw != confirm_pw:
        st.error("New passwords do not match.")
    else:
        ok, msg = change_password_action(user["id"], current_pw, new_pw)
        if ok:
            st.success(msg)
        else:
            st.error(msg)

st.divider()

# My recent predictions
st.subheader("My Recent Predictions")
preds = fetchall(
    """SELECT disease_type, prediction, confidence, model_version, timestamp
       FROM prediction_logs WHERE user_id=?
       ORDER BY timestamp DESC LIMIT 20""",
    (user["id"],)
)
if preds:
    df = pd.DataFrame(preds)
    df["prediction"] = df["prediction"].map({0: "Low Risk", 1: "High Risk"})
    df["confidence"] = df["confidence"].apply(lambda x: f"{x*100:.1f}%")
    st.dataframe(df, use_container_width=True, hide_index=True)
else:
    st.info("You have not made any predictions yet.")