"""
Run diabetes and heart disease predictions.
Accessible to: admin, doctor.
"""

import sys, os
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import render_sidebar
from auth_ui import require_role, current_user
from db   import execute

st.set_page_config(page_title="Predict · Healthcare Analytics", page_icon="🩺", layout="wide")
require_role("admin", "doctor")
user = current_user()
render_sidebar()

st.title("Chronic Disease Prediction")
st.caption("Enter anonymised clinical measurements - **no patient identifiers**.")
st.divider()


def _show_result(result: dict):
    """Render the prediction result card."""
    st.divider()
    risk = result["risk_level"]

    if risk == "Low Risk":
        st.success(f"## ✅ {risk}")
    elif risk == "Moderate Risk":
        st.warning(f"## ⚠️ {risk}")
    else:
        st.error(f"## 🚨 {risk}")

    col1, col2, col3 = st.columns(3)
    col1.metric("Prediction", "High Risk" if result["prediction"] == 1 else "Low Risk")
    col2.metric("Confidence", f"{result['confidence']*100:.1f}%")
    col3.metric("Probability", f"{result['probability']*100:.1f}%")

    st.info(f"**Clinical Interpretation:** {result['explanation']}")

    st.markdown("**Risk Probability**")
    prob = result["probability"]
    st.progress(prob, text=f"{prob*100:.1f}% probability of positive diagnosis")

    st.caption(
        f"⚕️ **Disclaimer:** {result['disclaimer']} "
        f"| Model: `{result['model_version']}`"
    )


# Check models are ready
try:
    from ml.predict import models_are_ready, predict_diabetes, predict_heart, DiabetesInput, HeartInput
    ready = models_are_ready()
except Exception as e:
    st.error(f"Could not load prediction module: {e}")
    st.stop()

if not ready:
    st.warning(
        "⚠️ Models have not been trained yet. "
        "An **admin** must go to the **FL Training** page and run training first."
    )
    st.stop()

# Disease selector
disease = st.radio(
    "Select disease to predict:",
    ["🩸 Diabetes", "❤️ Heart Disease"],
    horizontal=True,
)
st.divider()

# DIABETES FORM
if disease == "🩸 Diabetes":
    st.subheader("🩸 Diabetes Risk Assessment")
    st.caption("Features from the Pima Indian Diabetes dataset.")

    with st.form("diabetes_form"):
        c1, c2 = st.columns(2)
        with c1:
            pregnancies = st.number_input("Pregnancies", min_value=0, max_value=20, value=1, step=1, help="Number of times pregnant")
            glucose = st.number_input("Glucose (mg/dL)", min_value=1, max_value=300, value=100, help="Plasma glucose concentration (2hr oral glucose tolerance test)")
            bp = st.number_input("Blood Pressure (mmHg)", min_value=1, max_value=200, value=70, help="Diastolic blood pressure")
            skin = st.number_input("Skin Thickness (mm)", min_value=0, max_value=100, value=20, help="Triceps skinfold thickness")
        with c2:
            insulin = st.number_input("Insulin (μU/mL)", min_value=0, max_value=900, value=80, help="2-hour serum insulin")
            bmi = st.number_input("BMI (kg/m²)", min_value=1.0, max_value=70.0,value=25.0, format="%.1f", help="Body mass index")
            dpf = st.number_input("Diabetes Pedigree Function", min_value=0.0, max_value=3.0, value=0.5, format="%.3f", help="Genetic influence score")
            age = st.number_input("Age (years)", min_value=1, max_value=120, value=30, help="Patient age in years")

        submitted = st.form_submit_button("Run Prediction", use_container_width=True, type="primary")

    if submitted:
        with st.spinner("Running federated model inference…"):
            try:
                data = DiabetesInput(
                    Pregnancies=float(pregnancies), Glucose=float(glucose),
                    BloodPressure=float(bp), SkinThickness=float(skin),
                    Insulin=float(insulin), BMI=float(bmi),
                    DiabetesPedigreeFunction=float(dpf), Age=float(age),
                )
                result = predict_diabetes(data)
            except Exception as e:
                st.error(f"Prediction failed: {e}")
                st.stop()

        # Log to DB
        try:
            execute(
                """INSERT INTO prediction_logs
                   (user_id, disease_type, input_features, prediction, confidence, model_version, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?, datetime('now'))""",
                (user["id"], "diabetes", str(data.model_dump()),
                 result["prediction"], result["confidence"], result["model_version"])
            )
        except Exception:
            pass  # logging must not block the result

        _show_result(result)


# HEART DISEASE FORM
else:
    st.subheader("❤️ Heart Disease Risk Assessment")
    st.caption("Features from the Cleveland Heart Disease dataset.")

    with st.form("heart_form"):
        c1, c2 = st.columns(2)
        with c1:
            age = st.number_input("Age (years)", min_value=1, max_value=120, value=50)
            sex = st.selectbox("Sex", [0, 1], format_func=lambda x: "Female (0)" if x==0 else "Male (1)")
            cp = st.selectbox("Chest Pain Type (cp)", [0, 1, 2, 3], format_func=lambda x: f"Type {x}", help="0=Typical angina, 1=Atypical angina, 2=Non-anginal, 3=Asymptomatic")
            trestbps= st.number_input("Resting Blood Pressure (mmHg)", min_value=50, max_value=250, value=120)
            chol = st.number_input("Serum Cholesterol (mg/dL)", min_value=50, max_value=600, value=200)
            fbs = st.selectbox("Fasting Blood Sugar > 120 mg/dL", [0, 1], format_func=lambda x: "No (0)" if x==0 else "Yes (1)")
            restecg = st.selectbox("Resting ECG", [0, 1, 2], help="0=Normal, 1=ST-T wave abnormality, 2=Left ventricular hypertrophy")
        with c2:
            thalach = st.number_input("Max Heart Rate Achieved", min_value=50, max_value=250, value=150)
            exang = st.selectbox("Exercise Induced Angina", [0, 1], format_func=lambda x: "No (0)" if x==0 else "Yes (1)")
            oldpeak = st.number_input("ST Depression (oldpeak)", min_value=0.0, max_value=10.0, value=1.0, format="%.1f")
            slope = st.selectbox("Slope of Peak Exercise ST", [0, 1, 2], help="0=Upsloping, 1=Flat, 2=Downsloping")
            ca = st.selectbox("Major Vessels Coloured by Fluoroscopy (ca)", [0, 1, 2, 3])
            thal = st.selectbox("Thalassemia (thal)", [0, 1, 2, 3], help="0=Normal, 1=Fixed defect, 2=Reversable defect, 3=Unknown")

        submitted = st.form_submit_button("Run Prediction", use_container_width=True, type="primary")

    if submitted:
        with st.spinner("Running federated model inference…"):
            try:
                data   = HeartInput(
                    age=float(age), sex=int(sex), cp=int(cp), trestbps=float(trestbps),
                    chol=float(chol), fbs=int(fbs), restecg=int(restecg),
                    thalach=float(thalach), exang=int(exang), oldpeak=float(oldpeak),
                    slope=int(slope), ca=int(ca), thal=int(thal),
                )
                result = predict_heart(data)
            except Exception as e:
                st.error(f"Prediction failed: {e}")
                st.stop()

        try:
            execute(
                """INSERT INTO prediction_logs
                   (user_id, disease_type, input_features, prediction, confidence, model_version, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?, datetime('now'))""",
                (user["id"], "heart", str(data.model_dump()),
                 result["prediction"], result["confidence"], result["model_version"])
            )
        except Exception:
            pass

        _show_result(result)