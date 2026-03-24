"""
Federated Learning training control panel.
Accessible to: admin only.
"""

import sys, os
import streamlit as st
import plotly.express as px
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import render_sidebar
from auth_ui import require_role, current_user
from db   import execute

st.set_page_config(page_title="FL Training · Healthcare Analytics", page_icon="🤖", layout="wide")
require_role("admin")
user = current_user()
render_sidebar()

st.title("Federated Learning Training")
st.caption("Train the diabetes and heart disease models using the Federated Averaging algorithm.")
st.divider()

# Import FL modules
try:
    from federated.server import (
        read_fl_status,
        start_fl_training_background,
        run_federated_training_simulation,
    )
    from ml.preprocess import get_dataset_stats
    fl_available = True
except Exception as e:
    st.error(f"Could not load federated learning module: {e}")
    fl_available = False
    st.stop()

# Dataset info
st.subheader("Dataset Information")
try:
    stats = get_dataset_stats()
    col1, col2 = st.columns(2)
    with col1:
        d = stats["diabetes"]
        st.markdown("**🩸 Diabetes Dataset**")
        st.metric("Total Rows", d["total_rows"])
        st.metric("Train Split", d["train_size"])
        st.metric("Test Split", d["test_size"])
        dist = d["class_distribution"]
        st.caption(f"Class 0 (No Diabetes): {dist.get(0,'?')} | Class 1 (Diabetes): {dist.get(1,'?')}")
    with col2:
        h = stats["heart"]
        st.markdown("**❤️ Heart Disease Dataset**")
        st.metric("Total Rows", h["total_rows"])
        st.metric("Train Split", h["train_size"])
        st.metric("Test Split", h["test_size"])
        dist2 = h["class_distribution"]
        st.caption(f"Class 0 (No Disease): {dist2.get(0,'?')} | Class 1 (Disease): {dist2.get(1,'?')}")
except Exception as e:
    st.warning(f"Could not load dataset stats: {e}")

st.divider()

# Training control
st.subheader("Training Control")

status = read_fl_status()

col_status, col_btn = st.columns([2, 1])
with col_status:
    s = status.get("status", "not_started")
    if s == "not_started":
        st.info("Status: **Not started** — no models trained yet.")
    elif s == "training":
        rounds_done = status.get("rounds_completed", 0)
        total_rounds = status.get("total_rounds", "?")
        st.warning(f"Status: **Training in progress** · Round {rounds_done} / {total_rounds}")
    elif s == "complete":
        st.success(f"Status: **Complete** · {status.get('rounds_completed','?')} rounds finished.")

with col_btn:
    if s == "training":
        st.button("Training in Progress…", disabled=True, use_container_width=True)
    else:
        if st.button("Start Training", type="primary", use_container_width=True):
            with st.spinner("Starting federated training - this may take a minute…"):
                try:
                    execute(
                        """INSERT INTO audit_logs (user_id, action, success, timestamp)
                           VALUES (?,?,1,datetime('now'))""",
                        (user["id"], "FL_TRAINING_STARTED")
                    )
                    run_federated_training_simulation()
                    st.success("✅ Training complete! Models saved.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Training failed: {e}")

if s == "training":
    st.info("Refresh the page to check progress.")
    if st.button("Refresh Status"):
        st.rerun()

st.divider()

# Training metrics
if s == "complete":
    st.subheader("Training Results")

    final = status.get("final_metrics", {})
    if final:
        col_d, col_h = st.columns(2)

        with col_d:
            st.markdown("**🩸 Diabetes Model**")
            dm = final.get("diabetes", {})
            st.metric("Accuracy", f"{dm.get('accuracy',0)*100:.1f}%")
            st.metric("F1 Score", f"{dm.get('f1',0)*100:.1f}%")
            st.metric("AUC-ROC", f"{dm.get('auc',0)*100:.1f}%")
            st.caption(f"Test samples: {dm.get('test_samples','?')}")

        with col_h:
            st.markdown("**❤️ Heart Disease Model**")
            hm = final.get("heart", {})
            st.metric("Accuracy", f"{hm.get('accuracy',0)*100:.1f}%")
            st.metric("F1 Score", f"{hm.get('f1',0)*100:.1f}%")
            st.metric("AUC-ROC", f"{hm.get('auc',0)*100:.1f}%")
            st.caption(f"Test samples: {hm.get('test_samples','?')}")

    # Per-round chart from status rounds
    rounds_data = status.get("rounds", [])
    if rounds_data:
        st.subheader("Per-Round Accuracy")
        rows = []
        for r in rounds_data:
            rn = r.get("round", "?")
            for disease, metrics in r.get("clients", {}).items():
                rows.append({
                    "Round": rn,
                    "Disease": disease.capitalize(),
                    "Accuracy": metrics.get("accuracy", 0) * 100,
                })
        if rows:
            df = pd.DataFrame(rows)
            fig = px.line(
                df, x="Round", y="Accuracy", color="Disease",
                markers=True,
                labels={"Accuracy": "Accuracy (%)"},
                color_discrete_map={"Diabetes": "#2563EB", "Heart": "#DC2626"},
            )
            fig.update_layout(height=350, yaxis_range=[0, 105])
            st.plotly_chart(fig, use_container_width=True)

    st.divider()
    st.subheader("ℹ️ About This Model")
    st.markdown("""
    **Algorithm:** Federated Averaging (FedAvg)

    **Architecture:**
    - Each hospital client trains a **Logistic Regression** on its local data.
    - The server aggregates weights using **weighted averaging** by sample count.
    - Raw patient data **never leaves the local client** - only model weights are shared.

    **Clients:**
    - Hospital A -> Diabetes dataset (768 samples)
    - Hospital B -> Heart Disease dataset (1025 samples)
    """)