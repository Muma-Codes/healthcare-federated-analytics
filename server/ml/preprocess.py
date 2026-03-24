"""
Data preprocessing for federated learning clients.

Handles:
  - Loading diabetes.csv  (768 rows)
  - Loading heart.csv     (1025 rows)
  - Cleaning: zero-value imputation for medically invalid zeros
  - Train / test split    (80 / 20, stratified)
  - Standard scaling      (scaler fitted on train set only — no data leakage)
  - Returning numpy arrays ready for scikit-learn

No patient PII is ever processed here; both CSVs contain only
anonymised clinical measurements.
"""

import os
from dataclasses import dataclass
from typing import Tuple

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")

DIABETES_CSV = os.path.join(DATA_DIR, "diabetes.csv")
HEART_CSV = os.path.join(DATA_DIR, "heart.csv")

# Columns where a value of 0 is physiologically impossible -> replace with median
DIABETES_ZERO_IMPUTE = ["Glucose", "BloodPressure", "SkinThickness", "Insulin", "BMI"]
HEART_ZERO_IMPUTE: list[str] = []   # heart dataset has no such columns


@dataclass
class DataSplit:
    X_train: np.ndarray
    X_test:  np.ndarray
    y_train: np.ndarray
    y_test:  np.ndarray
    scaler:  StandardScaler
    feature_names: list[str]
    disease_type: str
    n_train: int
    n_test:  int


def _load_diabetes() -> pd.DataFrame:
    df = pd.read_csv(DIABETES_CSV)

    # Replace physiologically impossible zeros with column median
    for col in DIABETES_ZERO_IMPUTE:
        median = df[col].replace(0, np.nan).median()
        df[col] = df[col].replace(0, median)

    return df


def _load_heart() -> pd.DataFrame:
    df = pd.read_csv(HEART_CSV)
    df.dropna(inplace=True)
    return df


def prepare_diabetes(test_size: float = 0.2, random_state: int = 42) -> DataSplit:
    """
    Load, clean, split and scale the diabetes dataset.

    Features : Pregnancies, Glucose, BloodPressure, SkinThickness,
                Insulin, BMI, DiabetesPedigreeFunction, Age
    Target  : Outcome  (0 = no diabetes, 1 = diabetes)
    Train/Test: 80 / 20  stratified
    """
    df = _load_diabetes()
    feature_cols = [c for c in df.columns if c != "Outcome"]
    X = df[feature_cols].values
    y = df["Outcome"].values

    X_train, X_test, y_train, y_test = train_test_split(
        X, y,
        test_size=test_size,
        random_state=random_state,
        stratify=y,           # preserve class ratio in both splits
    )

    scaler = StandardScaler()
    X_train = scaler.fit_transform(X_train)   # fit ONLY on training data
    X_test  = scaler.transform(X_test)         # apply same transform to test

    return DataSplit(
        X_train=X_train,
        X_test=X_test,
        y_train=y_train,
        y_test=y_test,
        scaler=scaler,
        feature_names=feature_cols,
        disease_type="diabetes",
        n_train=len(X_train),
        n_test=len(X_test),
    )


def prepare_heart(test_size: float = 0.2, random_state: int = 42) -> DataSplit:
    """
    Load, clean, split and scale the heart disease dataset.

    Features : age, sex, cp, trestbps, chol, fbs, restecg,
                thalach, exang, oldpeak, slope, ca, thal
    Target : target  (0 = no disease, 1 = disease)
    Train/Test: 80 / 20 stratified
    """
    df = _load_heart()
    feature_cols = [c for c in df.columns if c != "target"]
    X = df[feature_cols].values
    y = df["target"].values

    X_train, X_test, y_train, y_test = train_test_split(
        X, y,
        test_size=test_size,
        random_state=random_state,
        stratify=y,
    )

    scaler = StandardScaler()
    X_train = scaler.fit_transform(X_train)
    X_test = scaler.transform(X_test)

    return DataSplit(
        X_train=X_train,
        X_test=X_test,
        y_train=y_train,
        y_test=y_test,
        scaler=scaler,
        feature_names=feature_cols,
        disease_type="heart",
        n_train=len(X_train),
        n_test=len(X_test),
    )


def get_dataset_stats() -> dict:
    """Return summary statistics about both datasets (no raw data exposed)."""
    d = _load_diabetes()
    h = _load_heart()
    return {
        "diabetes": {
            "total_rows": len(d),
            "features": [c for c in d.columns if c != "Outcome"],
            "target_column": "Outcome",
            "class_distribution": d["Outcome"].value_counts().to_dict(),
            "train_size": int(len(d) * 0.8),
            "test_size": int(len(d) * 0.2),
        },
        "heart": {
            "total_rows": len(h),
            "features": [c for c in h.columns if c != "target"],
            "target_column": "target",
            "class_distribution": h["target"].value_counts().to_dict(),
            "train_size": int(len(h) * 0.8),
            "test_size": int(len(h) * 0.2),
        },
    }