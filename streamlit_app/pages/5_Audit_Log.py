"""
Paginated audit trail.
Accessible to: admin only.
"""

import sys, os
import streamlit as st
import pandas as pd
import plotly.express as px

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import render_sidebar
from auth_ui import require_role, current_user
from db   import fetchall, fetchone

st.set_page_config(page_title="Audit Log · Healthcare Analytics", page_icon="📋", layout="wide")
require_role("admin")
user = current_user()
render_sidebar()

st.title("Audit Log")
st.caption("Immutable record of all significant system actions.")
st.divider()

# Filters
col1, col2, col3 = st.columns(3)

with col1:
    action_filter = st.text_input("Filter by Action", placeholder="e.g. LOGIN_FAIL")
with col2:
    username_filter = st.text_input("Filter by Username", placeholder="e.g. admin")
with col3:
    success_filter = st.selectbox("Status", ["All", "Success", "Failed"])

page_size = 50
page = st.number_input("Page", min_value=1, value=1, step=1)
offset = (page - 1) * page_size

# Build query dynamically
conditions = []
params = []

if action_filter:
    conditions.append("a.action LIKE ?")
    params.append(f"%{action_filter}%")
if username_filter:
    conditions.append("u.username LIKE ?")
    params.append(f"%{username_filter}%")
if success_filter == "Success":
    conditions.append("a.success = 1")
elif success_filter == "Failed":
    conditions.append("a.success = 0")

where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

total = fetchone(
    f"SELECT COUNT(*) AS c FROM audit_logs a LEFT JOIN users u ON a.user_id=u.id {where}",
    tuple(params)
)["c"]

logs = fetchall(
    f"""SELECT a.timestamp, u.username, a.action, a.resource,
               a.detail, a.ip_address, a.success
        FROM audit_logs a
        LEFT JOIN users u ON a.user_id = u.id
        {where}
        ORDER BY a.timestamp DESC
        LIMIT {page_size} OFFSET {offset}""",
    tuple(params)
)

# Display
total_pages = max(1, (total + page_size - 1) // page_size)
st.caption(f"Showing page **{page}** of **{total_pages}** · {total} total records")

if logs:
    df = pd.DataFrame(logs)
    df["success"] = df["success"].map({1: "Success", 0: "Failed"})
    df.columns    = ["Timestamp", "User", "Action", "Resource", "Detail", "IP", "Status"]
    st.dataframe(df, use_container_width=True, hide_index=True)
else:
    st.info("No audit log entries match the current filters.")

# Summary charts
st.divider()
st.subheader("Action Frequency (All Time)")

action_counts = fetchall(
    "SELECT action, COUNT(*) AS n FROM audit_logs GROUP BY action ORDER BY n DESC LIMIT 15"
)
if action_counts:
    df_ac = pd.DataFrame(action_counts)
    fig = px.bar(
        df_ac, x="n", y="action", orientation="h",
        labels={"n": "Count", "action": "Action"},
        color="n",
        color_continuous_scale="Blues",
    )
    fig.update_layout(height=400, margin=dict(t=10, b=10), showlegend=False)
    st.plotly_chart(fig, use_container_width=True)