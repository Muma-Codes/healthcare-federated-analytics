"""
Shared helpers used by every Streamlit page.

Imported at the top of each page BEFORE other local imports
so the server package is always on sys.path.
"""

import sys
import os

# Ensure server/ is importable
# Works whether the page is at pages/X.py or streamlit_app/X.py
_THIS_DIR    = os.path.dirname(os.path.abspath(__file__))
# If called from pages/ sub-directory, go up one more level
if os.path.basename(_THIS_DIR) == "pages":
    _STREAMLIT_DIR = os.path.dirname(_THIS_DIR)
else:
    _STREAMLIT_DIR = _THIS_DIR

_PROJECT_ROOT = os.path.dirname(_STREAMLIT_DIR)
_SERVER_DIR   = os.path.join(_PROJECT_ROOT, "server")

for _p in [_SERVER_DIR, _STREAMLIT_DIR]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Sidebar renderer
import streamlit as st
from auth_ui import current_user, logout


def render_sidebar():
    """
    Render the standard sidebar with user info and logout button.
    """
    user = current_user()
    if not user:
        return

    with st.sidebar:
        st.markdown(
            f"""
            <div style='display:flex; align-items:center; gap:10px; padding:6px 0 4px 0;'>
                <div style='background:#2563EB; color:white; border-radius:50%;
                            width:38px; height:38px; display:flex; align-items:center;
                            justify-content:center; font-size:1.1rem; flex-shrink:0;'>
                    {user['full_name'][0].upper()}
                </div>
                <div>
                    <div style='font-weight:600; font-size:0.95rem;'>{user['full_name']}</div>
                    <div style='font-size:0.78rem; color:#64748B;'>{user['role'].capitalize()}</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.divider()

        # Navigation links
        st.page_link("app.py", label="Home")
        st.page_link("pages/1_Dashboard.py", label="Dashboard")

        if user["role"] in ("admin", "doctor"):
            st.page_link("pages/2_Predict.py", label="Predict")

        st.page_link("pages/3_Profile.py", label="Profile")

        if user["role"] == "admin":
            st.page_link("pages/4_Users.py", label="Users")
            st.page_link("pages/5_Audit_Log.py", label="Audit Log")

        st.page_link("pages/6_Security_Training.py", label="Security Training")

        if user["role"] == "admin":
            st.page_link("pages/7_FL_Training.py", label="FL Training")

        st.divider()

        # Training compliance warning
        if not user.get("last_training_date"):
            st.warning("No security training on record.", icon="🛡️")

        if st.button("Logout", use_container_width=True, type="secondary"):
            logout()