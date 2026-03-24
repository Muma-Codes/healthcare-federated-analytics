"""
Security awareness training with quiz.
Accessible to all authenticated roles.
"""

import sys, os
import streamlit as st
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import render_sidebar
from auth_ui import require_login, current_user
from db   import fetchone, execute

st.set_page_config(page_title="Security Training · Healthcare Analytics", page_icon="🛡️", layout="wide")
require_login()
user = current_user()
render_sidebar()

st.title("Security Awareness Training")
st.divider()

# Training status banner
db_user = fetchone("SELECT last_training_date FROM users WHERE id=?", (user["id"],))
last_date = db_user["last_training_date"]

if last_date:
    last_dt = datetime.fromisoformat(last_date.replace("Z", "+00:00")) if "+" in last_date or "Z" in last_date \
                else datetime.fromisoformat(last_date).replace(tzinfo=timezone.utc)
    days_since = (datetime.now(timezone.utc) - last_dt).days
    is_current = days_since <= 365
    if is_current:
        st.success(f"Training is **current**. Last completed {days_since} day(s) ago.")
    else:
        st.error(f"⚠️ Training has **expired** ({days_since} days ago). Please re-complete it.")
else:
    st.warning("⚠️ No training on record. Please complete the module below.")

st.divider()

# Training material
with st.expander("Training Material - Read before taking the quiz", expanded=True):
    st.markdown("""
    ### 1. Patient Data Privacy
    - **Never** share patient data outside authorised systems.
    - Clinical measurements must be **anonymised** before processing.
    - The Federated Learning approach ensures raw patient data **never leaves the hospital**.

    ### 2. Access Control
    - Use your credentials only. **Never share passwords**.
    - Doctors can run predictions; nurses have read-only access.
    - Admins are responsible for approving accounts and reviewing audit logs.

    ### 3. Password Policy
    - Passwords must be >= 8 characters with uppercase, lowercase, digit and special character.
    - Passwords **expire every 90 days**. Change yours before it expires.
    - After **5 failed login attempts**, your account will be locked automatically.

    ### 4. Multi-Factor Authentication (MFA)
    - MFA adds an extra layer of security using a TOTP authenticator app.
    - Enabling MFA is **strongly recommended** for all accounts.
    - Never share your TOTP codes with anyone.

    ### 5. Incident Reporting
    - If you suspect a security breach, **report immediately** to the system administrator.
    - All actions in the system are logged in the audit trail.
    - Suspicious login attempts are flagged automatically.
    """)

st.divider()

# Quiz
st.subheader("Knowledge Quiz")
st.caption("You need to score **at least 4 out of 5** to pass. Good luck!")

QUESTIONS = [
    {
        "q": "Q1. What does Federated Learning ensure about patient data?",
        "options": [
            "A. Patient data is uploaded to a central server",
            "B. Raw patient data never leaves the hospital",
            "C. Patient data is deleted after training",
            "D. Patient data is encrypted and shared",
        ],
        "answer": "B. Raw patient data never leaves the hospital",
    },
    {
        "q": "Q2. After how many failed login attempts is an account locked?",
        "options": ["A. 3", "B. 10", "C. 5", "D. 7"],
        "answer": "C. 5",
    },
    {
        "q": "Q3. Which role can run disease predictions?",
        "options": [
            "A. Nurse only",
            "B. Any logged-in user",
            "C. Admin and Doctor",
            "D. Admin only",
        ],
        "answer": "C. Admin and Doctor",
    },
    {
        "q": "Q4. How often do passwords expire in this system?",
        "options": ["A. 30 days", "B. 180 days", "C. Never", "D. 90 days"],
        "answer": "D. 90 days",
    },
    {
        "q": "Q5. What should you do if you suspect a security breach?",
        "options": [
            "A. Ignore it - the system will detect it automatically",
            "B. Delete your account and create a new one",
            "C. Report immediately to the system administrator",
            "D. Change your password and continue working",
        ],
        "answer": "C. Report immediately to the system administrator",
    },
]

with st.form("quiz_form"):
    answers = {}
    for i, q in enumerate(QUESTIONS):
        st.markdown(f"**{q['q']}**")
        answers[i] = st.radio(
            label=f"answer_{i}",
            options=q["options"],
            key=f"q{i}",
            label_visibility="collapsed",
        )
        st.write("")

    quiz_submit = st.form_submit_button("Submit Quiz", type="primary", use_container_width=True)

if quiz_submit:
    score = sum(1 for i, q in enumerate(QUESTIONS) if answers[i] == q["answer"])
    passed = score >= 4

    if passed:
        st.balloons()
        st.success(f"🎉 **Passed!** You scored **{score}/5**. Your training record has been updated.")
        execute(
            "UPDATE users SET last_training_date=datetime('now') WHERE id=?",
            (user["id"],)
        )
    else:
        st.error(f"❌ **Failed.** You scored **{score}/5**. Please review the material and try again.")

    # Log the attempt
    execute(
        """INSERT INTO training_completions (user_id, score, passed, completed_at)
           VALUES (?, ?, ?, datetime('now'))""",
        (user["id"], score, int(passed))
    )
    execute(
        """INSERT INTO audit_logs (user_id, action, detail, success, timestamp)
           VALUES (?,?,?,?,datetime('now'))""",
        (user["id"], "TRAINING_COMPLETED", f"score={score}/5 passed={passed}", 1)
    )

    # Show correct answers
    st.divider()
    st.subheader("Answer Review")
    for i, q in enumerate(QUESTIONS):
        user_ans = answers[i]
        correct = q["answer"]
        is_correct = user_ans == correct
        icon = "✅" if is_correct else "❌"
        st.markdown(f"{icon} **{q['q']}**")
        if not is_correct:
            st.caption(f"Your answer: {user_ans}  |  Correct: {correct}")