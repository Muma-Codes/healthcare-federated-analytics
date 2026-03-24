"""
Prediction module.

Loads the trained federated models from disk and runs inference.
Input features are validated, scaled using the saved scaler,
then passed to the appropriate model.

PRIVACY: This module never receives or stores patient names / IDs.
Only anonymised clinical measurements are processed.
"""

import os
import pickle
from typing import Any, Dict

import numpy as np
from pydantic import BaseModel, field_validator

# Model paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS_DIR = os.path.join(BASE_DIR, "models")

DIABETES_MODEL_PATH = os.path.join(MODELS_DIR, "diabetes_model.pkl")
HEART_MODEL_PATH = os.path.join(MODELS_DIR, "heart_model.pkl")
SCALER_DIABETES = os.path.join(MODELS_DIR, "scaler_diabetes.pkl")
SCALER_HEART = os.path.join(MODELS_DIR, "scaler_heart.pkl")


# Input schemas

class DiabetesInput(BaseModel):
    """
    Clinical measurements for diabetes risk prediction.
    Field names match the diabetes.csv column names exactly.
    NO personal identifiers - only anonymised measurements.
    """
    Pregnancies: float
    Glucose: float
    BloodPressure: float
    SkinThickness: float
    Insulin: float
    BMI: float
    DiabetesPedigreeFunction: float
    Age: float

    @field_validator("Glucose", "BloodPressure", "BMI")
    @classmethod
    def must_be_positive(cls, v, info):
        if v <= 0:
            raise ValueError(f"{info.field_name} must be greater than 0.")
        return v

    def to_array(self) -> np.ndarray:
        return np.array([[
            self.Pregnancies,
            self.Glucose,
            self.BloodPressure,
            self.SkinThickness,
            self.Insulin,
            self.BMI,
            self.DiabetesPedigreeFunction,
            self.Age,
        ]])


class HeartInput(BaseModel):
    """
    Clinical measurements for heart disease risk prediction.
    Field names match the heart.csv column names exactly.
    NO personal identifiers - only anonymised measurements.
    """
    age:      float
    sex:      int       # 0 = female, 1 = male
    cp:       int       # chest pain type 0-3
    trestbps: float     # resting blood pressure
    chol:     float     # serum cholesterol
    fbs:      int       # fasting blood sugar > 120 mg/dl (1=yes, 0=no)
    restecg:  int       # resting ECG results 0-2
    thalach:  float     # maximum heart rate achieved
    exang:    int       # exercise induced angina (1=yes, 0=no)
    oldpeak:  float     # ST depression
    slope:    int       # slope of peak exercise ST segment 0-2
    ca:       int       # number of major vessels 0-3
    thal:     int       # thalassemia 0-3

    @field_validator("cp")
    @classmethod
    def validate_cp(cls, v):
        if v not in (0, 1, 2, 3):
            raise ValueError("cp must be 0, 1, 2, or 3.")
        return v

    def to_array(self) -> np.ndarray:
        return np.array([[
            self.age, self.sex, self.cp, self.trestbps, self.chol,
            self.fbs, self.restecg, self.thalach, self.exang,
            self.oldpeak, self.slope, self.ca, self.thal,
        ]])


# Prediction helpers

def _load_model(path: str):
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Model not found at {path}. "
            "Please run federated training first via POST /federated/train."
        )
    with open(path, "rb") as f:
        return pickle.load(f)


def _load_scaler(path: str):
    if not os.path.exists(path):
        raise FileNotFoundError(f"Scaler not found at {path}.")
    with open(path, "rb") as f:
        return pickle.load(f)


def predict_diabetes(data: DiabetesInput) -> Dict[str, Any]:
    """
    Run diabetes risk prediction.

    Returns:
      prediction : 0 (low risk) or 1 (high risk)
      confidence : probability of the predicted class
      risk_level : "Low Risk" | "Moderate Risk" | "High Risk"
      explanation : brief clinical interpretation
    """
    model = _load_model(DIABETES_MODEL_PATH)
    scaler = _load_scaler(SCALER_DIABETES)

    X = data.to_array()
    X_scaled = scaler.transform(X)

    prediction = int(model.predict(X_scaled)[0])
    proba = model.predict_proba(X_scaled)[0]
    confidence = float(proba[prediction])

    # Risk level based on probability of positive class
    pos_prob = float(proba[1])
    if pos_prob < 0.35:
        risk_level  = "Low Risk"
        explanation = "Clinical measurements suggest a low probability of diabetes onset."
    elif pos_prob < 0.65:
        risk_level  = "Moderate Risk"
        explanation = "Some indicators warrant monitoring. Recommend follow-up testing."
    else:
        risk_level  = "High Risk"
        explanation = "Multiple indicators suggest elevated diabetes risk. Recommend clinical evaluation."

    return {
        "prediction": prediction,
        "confidence": round(confidence, 4),
        "probability": round(pos_prob, 4),
        "risk_level": risk_level,
        "explanation": explanation,
        "disease_type": "diabetes",
        "model_version": "federated-v1",
        "disclaimer": (
            "This is a decision-support tool only and does NOT constitute "
            "a medical diagnosis. Always consult a qualified healthcare professional."
        ),
    }


def predict_heart(data: HeartInput) -> Dict[str, Any]:
    """Run heart disease risk prediction."""
    model = _load_model(HEART_MODEL_PATH)
    scaler = _load_scaler(SCALER_HEART)

    X = data.to_array()
    X_scaled = scaler.transform(X)

    prediction = int(model.predict(X_scaled)[0])
    proba = model.predict_proba(X_scaled)[0]
    confidence = float(proba[prediction])
    pos_prob = float(proba[1])

    if pos_prob < 0.35:
        risk_level = "Low Risk"
        explanation = "Cardiac indicators suggest a low probability of heart disease."
    elif pos_prob < 0.65:
        risk_level = "Moderate Risk"
        explanation = "Some cardiac indicators warrant further assessment."
    else:
        risk_level = "High Risk"
        explanation = "Multiple cardiac risk factors detected. Recommend urgent clinical evaluation."

    return {
        "prediction": prediction,
        "confidence": round(confidence, 4),
        "probability": round(pos_prob, 4),
        "risk_level": risk_level,
        "explanation": explanation,
        "disease_type": "heart",
        "model_version": "federated-v1",
        "disclaimer": (
            "This is a decision-support tool only and does NOT constitute "
            "a medical diagnosis. Always consult a qualified healthcare professional."
        ),
    }


def models_are_ready() -> bool:
    return (
        os.path.exists(DIABETES_MODEL_PATH)
        and os.path.exists(HEART_MODEL_PATH)
        and os.path.exists(SCALER_DIABETES)
        and os.path.exists(SCALER_HEART)
    )