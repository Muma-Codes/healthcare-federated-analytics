"""
Entry point for the Streamlit frontend.

Shows the Login / Sign-Up screen.
Once logged in, Streamlit's multi-page navigation takes over
and the user sees the sidebar with all pages they are allowed to visit.
"""

import streamlit as st
from auth_ui import init_session, is_logged_in, login, register

st.set_page_config(
    page_title="Healthcare Analytics",
    page_icon="🏥",
    layout="centered",
    initial_sidebar_state="collapsed",
)

init_session()

# Database health check
from db import db_ok
ok, db_err = db_ok()
if not ok:
    st.error("### Database Not Found")
    st.markdown(db_err)
    st.stop()

# Already logged in -> send to dashboard
if is_logged_in():
    st.switch_page("pages/1_Dashboard.py")

# Landing header
st.markdown(
    """
    <div style='text-align:center; padding: 2rem 0 1rem 0;'>
        <h1 style='font-size:2.4rem; color:#2563EB;'>Healthcare Analytics</h1>
        <p style='color:#64748B; font-size:1.05rem;'>
            Federated Learning · Chronic Disease Prediction · Privacy-Preserving
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

st.divider()

tab_login, tab_signup = st.tabs(["Login", "Sign Up"])

# Login tab
with tab_login:
    st.subheader("Sign in to your account")
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login", use_container_width=True, type="primary")

    if submitted:
        if not username or not password:
            st.error("Please enter both username and password.")
        else:
            with st.spinner("Authenticating…"):
                ok, msg = login(username, password)
            if ok:
                st.success(msg)
                st.switch_page("pages/1_Dashboard.py")
            else:
                st.error(msg)

# Sign-Up tab
with tab_signup:
    st.subheader("Create a new account")
    st.info(
        "After registering, your account will be **pending approval**. "
        "An administrator must assign your role before you can log in.",
        icon="ℹ️",
    )
    with st.form("signup_form"):
        col1, col2 = st.columns(2)
        with col1:
            new_username  = st.text_input("Username")
            new_email     = st.text_input("Email")
        with col2:
            new_full_name = st.text_input("Full Name")
            new_password  = st.text_input("Password", type="password")

        st.caption(
            "Password must be greater than or equal to 8 characters and include "
            "uppercase, lowercase, digit and special character."
        )
        reg_submitted = st.form_submit_button("Create Account", use_container_width=True, type="primary")

    if reg_submitted:
        if not all([new_username, new_email, new_full_name, new_password]):
            st.error("All fields are required.")
        else:
            with st.spinner("Creating account…"):
                ok, msg = register(new_username, new_email, new_full_name, new_password)
            if ok:
                st.success(msg)
            else:
                st.error(msg)