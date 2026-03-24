"""
Summary stats and recent activity.
Accessible to all authenticated roles.
"""

import sys, os
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import render_sidebar
from auth_ui import require_login, current_user
from db   import fetchone, fetchall

st.set_page_config(page_title="Dashboard · Healthcare Analytics", page_icon="📊", layout="wide")
require_login()
user = current_user()
render_sidebar()

# Page header
st.title("Dashboard")
st.caption(f"Welcome back, **{user['full_name']}**  ·  {datetime.now().strftime('%A, %d %B %Y')}")
st.divider()

# Fetch stats
total_users = fetchone("SELECT COUNT(*) AS c FROM users")["c"]
active_users = fetchone("SELECT COUNT(*) AS c FROM users WHERE is_active=1")["c"]
pending = fetchone("SELECT COUNT(*) AS c FROM users WHERE role='pending'")["c"]
locked = fetchone("SELECT COUNT(*) AS c FROM users WHERE is_locked=1")["c"]

total_preds = fetchone("SELECT COUNT(*) AS c FROM prediction_logs")["c"]
today = datetime.utcnow().date().isoformat()
today_preds = fetchone(
    "SELECT COUNT(*) AS c FROM prediction_logs WHERE date(timestamp)=?", (today,)
)["c"]
diab_preds = fetchone(
    "SELECT COUNT(*) AS c FROM prediction_logs WHERE disease_type='diabetes'"
)["c"]
heart_preds = fetchone(
    "SELECT COUNT(*) AS c FROM prediction_logs WHERE disease_type='heart'"
)["c"]

failed_today = fetchone(
    "SELECT COUNT(*) AS c FROM audit_logs WHERE action='LOGIN_FAIL' AND date(timestamp)=?",
    (today,)
)["c"]

# Training compliance (trained within last 365 days)
compliant = fetchone(
    "SELECT COUNT(*) AS c FROM users WHERE is_active=1 AND "
    "last_training_date >= date('now', '-365 days')"
)["c"]
non_compliant = active_users - compliant

# Metric cards
st.subheader("Users")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Users", total_users)
c2.metric("Active", active_users)
c3.metric("Pending Approval", pending,  delta=f"{'⚠️ ' if pending else ''}needs review" if pending else None)
c4.metric("Locked Accounts", locked,  delta="action needed" if locked else None)

st.divider()

st.subheader("Predictions")
p1, p2, p3, p4 = st.columns(4)
p1.metric("Total Predictions", total_preds)
p2.metric("Today's Predictions", today_preds)
p3.metric("Diabetes Predictions", diab_preds)
p4.metric("Heart Predictions", heart_preds)

st.divider()

st.subheader("Security")
s1, s2, s3 = st.columns(3)
s1.metric("Failed Logins Today", failed_today, delta="investigate" if failed_today > 3 else None)
s2.metric("Training Compliant", compliant)
s3.metric("Training Non-Compliant", non_compliant, delta="remind users" if non_compliant else None)

st.divider()

# Charts
col_left, col_right = st.columns(2)

with col_left:
    st.subheader("Prediction Distribution")
    if total_preds > 0:
        fig = px.pie(
            values=[diab_preds, heart_preds],
            names=["Diabetes", "Heart Disease"],
            color_discrete_sequence=["#2563EB", "#7C3AED"],
            hole=0.4,
        )
        fig.update_layout(margin=dict(t=20, b=20), height=280)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No predictions yet.")

with col_right:
    st.subheader("Predictions - Last 7 Days")
    rows = fetchall(
        """SELECT date(timestamp) AS day, COUNT(*) AS n
           FROM prediction_logs
           WHERE timestamp >= date('now', '-7 days')
           GROUP BY day ORDER BY day"""
    )
    if rows:
        df = pd.DataFrame(rows)
        fig2 = px.bar(
            df, x="day", y="n",
            labels={"day": "Date", "n": "Predictions"},
            color_discrete_sequence=["#2563EB"],
        )
        fig2.update_layout(margin=dict(t=20, b=20), height=280)
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("No prediction data for the last 7 days.")

# Recent audit activity
if user["role"] == "admin":
    st.subheader("Recent Activity")
    logs = fetchall(
        """SELECT a.timestamp, u.username, a.action, a.detail, a.success
           FROM audit_logs a LEFT JOIN users u ON a.user_id = u.id
           ORDER BY a.timestamp DESC LIMIT 10"""
    )
    if logs:
        df_logs = pd.DataFrame(logs)
        df_logs["success"] = df_logs["success"].map({1: "✅", 0: "❌"})
        st.dataframe(df_logs, use_container_width=True, hide_index=True)
    else:
        st.info("No recent activity.")