"""
Complete test suite — run with:  pytest tests/ -v

Coverage:
  1. Auth utilities   (hashing, JWT, TOTP, AES)
  2. ML preprocessing (data loading, train/test split, no leakage)
  3. Federated training simulation (FL rounds, metrics, model persistence)
  4. Predictions      (diabetes + heart, input validation)
  5. API — Auth       (register, login, pending-approval block, logout)
  6. API — Federated  (dataset-info, predict RBAC)
  7. API — Admin      (user list, pending list, role assignment, audit logs)
  8. API — Training   (quiz submit, status)
"""

import os
import sys

import numpy as np
import pytest
from fastapi.testclient import TestClient

# Path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Test environment variables - MUST be set before importing app modules
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests-32chars!!")
os.environ.setdefault("ENCRYPTION_KEY", "test-enc-key-0000")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_healthcare.db")
os.environ.setdefault("FL_ROUNDS", "2")
os.environ.setdefault("SMTP_USER", "")
os.environ.setdefault("SMTP_PASSWORD", "")
os.environ.setdefault("ALERT_EMAIL", "")


# 1. AUTH UTILITIES

class TestAuthUtils:

    def test_hash_and_verify_correct(self):
        from auth.utils import hash_password, verify_password
        h = hash_password("Secure@Pass1")
        assert verify_password("Secure@Pass1", h) is True

    def test_verify_wrong_password(self):
        from auth.utils import hash_password, verify_password
        h = hash_password("Secure@Pass1")
        assert verify_password("WrongPass!", h) is False

    def test_password_strength_valid(self):
        from auth.utils import validate_password_strength
        ok, _ = validate_password_strength("Secure@Pass1")
        assert ok is True

    def test_password_strength_too_short(self):
        from auth.utils import validate_password_strength
        ok, msg = validate_password_strength("Ab@1")
        assert ok is False
        assert "8" in msg

    def test_password_strength_no_special_char(self):
        from auth.utils import validate_password_strength
        ok, _ = validate_password_strength("SecurePass1")
        assert ok is False

    def test_jwt_roundtrip(self):
        from auth.utils import create_access_token, decode_access_token
        token = create_access_token({"sub": "99", "role": "doctor"})
        data  = decode_access_token(token)
        assert data["sub"]  == "99"
        assert data["role"] == "doctor"

    def test_jwt_invalid_returns_none(self):
        from auth.utils import decode_access_token
        assert decode_access_token("bad.token.value") is None

    def test_totp_correct_code(self):
        import pyotp
        from auth.utils import generate_totp_secret, verify_totp
        secret = generate_totp_secret()
        code   = pyotp.TOTP(secret).now()
        assert verify_totp(secret, code) is True

    def test_totp_wrong_code(self):
        from auth.utils import generate_totp_secret, verify_totp
        secret = generate_totp_secret()
        assert verify_totp(secret, "000000") is False

    def test_aes_encrypt_decrypt(self):
        from auth.utils import encrypt_text, decrypt_text
        plain = '{"Glucose": 120, "BMI": 28.5}'
        assert decrypt_text(encrypt_text(plain)) == plain

    def test_password_expiry_none(self):
        from auth.utils import is_password_expired
        assert is_password_expired(None) is True

    def test_password_not_expired_recent(self):
        from auth.utils import is_password_expired
        from datetime import datetime, timedelta, timezone
        assert is_password_expired(datetime.now(timezone.utc) - timedelta(days=10)) is False

    def test_password_expired_old(self):
        from auth.utils import is_password_expired
        from datetime import datetime, timedelta, timezone
        assert is_password_expired(datetime.now(timezone.utc) - timedelta(days=100)) is True


# 2. ML PREPROCESSING

class TestPreprocessing:

    def test_diabetes_feature_count(self):
        from ml.preprocess import prepare_diabetes
        d = prepare_diabetes()
        assert d.X_train.shape[1] == 8

    def test_diabetes_split_ratio(self):
        from ml.preprocess import prepare_diabetes
        d = prepare_diabetes()
        ratio = d.n_test / (d.n_train + d.n_test)
        assert abs(ratio - 0.2) < 0.02

    def test_no_data_leakage_diabetes(self):
        """StandardScaler fit on train only → train mean ≈ 0."""
        from ml.preprocess import prepare_diabetes
        d = prepare_diabetes()
        assert np.abs(d.X_train.mean(axis=0)).max() < 0.01

    def test_heart_feature_count(self):
        from ml.preprocess import prepare_heart
        h = prepare_heart()
        assert h.X_train.shape[1] == 13

    def test_stratified_split_diabetes(self):
        from ml.preprocess import prepare_diabetes
        d = prepare_diabetes()
        assert abs(d.y_train.mean() - d.y_test.mean()) < 0.05

    def test_stratified_split_heart(self):
        from ml.preprocess import prepare_heart
        h = prepare_heart()
        assert abs(h.y_train.mean() - h.y_test.mean()) < 0.05

    def test_zero_imputation(self):
        from ml.preprocess import _load_diabetes, DIABETES_ZERO_IMPUTE
        df = _load_diabetes()
        for col in DIABETES_ZERO_IMPUTE:
            assert df[col].min() > 0, f"{col} still has zeros after imputation"

    def test_dataset_stats_structure(self):
        from ml.preprocess import get_dataset_stats
        s = get_dataset_stats()
        assert s["diabetes"]["total_rows"] == 768
        assert s["heart"]["total_rows"]    == 1025


# 3. FEDERATED TRAINING

class TestFederatedTraining:

    def test_simulation_produces_rounds(self):
        from federated.server import run_federated_training_simulation
        r = run_federated_training_simulation()
        assert len(r["rounds"]) == 2

    def test_final_metrics_diabetes_valid(self):
        from federated.server import run_federated_training_simulation
        r = run_federated_training_simulation()
        dm = r["final_metrics"]["diabetes"]
        assert 0 <= dm["accuracy"] <= 1
        assert 0 <= dm["f1"]       <= 1
        assert 0 <= dm["auc"]      <= 1

    def test_final_metrics_heart_valid(self):
        from federated.server import run_federated_training_simulation
        r = run_federated_training_simulation()
        hm = r["final_metrics"]["heart"]
        assert 0 <= hm["accuracy"] <= 1

    def test_model_files_saved(self):
        from federated.server import (
            run_federated_training_simulation,
            DIABETES_MODEL_PATH, HEART_MODEL_PATH,
            SCALER_DIABETES, SCALER_HEART,
        )
        run_federated_training_simulation()
        for path in [DIABETES_MODEL_PATH, HEART_MODEL_PATH, SCALER_DIABETES, SCALER_HEART]:
            assert os.path.exists(path), f"Missing: {path}"

    def test_fl_status_complete(self):
        from federated.server import run_federated_training_simulation, read_fl_status
        run_federated_training_simulation()
        assert read_fl_status()["status"] == "complete"


# 4. PREDICTIONS

class TestPredictions:

    @classmethod
    def setup_class(cls):
        from federated.server import run_federated_training_simulation
        from ml.predict import models_are_ready
        if not models_are_ready():
            run_federated_training_simulation()

    def test_diabetes_low_risk(self):
        from ml.predict import DiabetesInput, predict_diabetes
        result = predict_diabetes(DiabetesInput(
            Pregnancies=1, Glucose=85, BloodPressure=66, SkinThickness=29,
            Insulin=0, BMI=26.6, DiabetesPedigreeFunction=0.351, Age=21,
        ))
        assert result["prediction"] in (0, 1)
        assert 0 <= result["confidence"] <= 1
        assert result["risk_level"] in ("Low Risk", "Moderate Risk", "High Risk")
        assert "disclaimer" in result

    def test_diabetes_has_disease_type(self):
        from ml.predict import DiabetesInput, predict_diabetes
        result = predict_diabetes(DiabetesInput(
            Pregnancies=8, Glucose=183, BloodPressure=64, SkinThickness=0,
            Insulin=0, BMI=23.3, DiabetesPedigreeFunction=0.672, Age=32,
        ))
        assert result["disease_type"] == "diabetes"

    def test_heart_prediction_structure(self):
        from ml.predict import HeartInput, predict_heart
        result = predict_heart(HeartInput(
            age=52, sex=1, cp=0, trestbps=125, chol=212, fbs=0,
            restecg=1, thalach=168, exang=0, oldpeak=1.0,
            slope=2, ca=2, thal=3,
        ))
        assert result["prediction"] in (0, 1)
        assert result["disease_type"] == "heart"

    def test_diabetes_invalid_glucose_raises(self):
        from ml.predict import DiabetesInput
        with pytest.raises(Exception):
            DiabetesInput(
                Pregnancies=1, Glucose=0,  # invalid: glucose cannot be 0
                BloodPressure=70, SkinThickness=20,
                Insulin=80, BMI=25.0, DiabetesPedigreeFunction=0.5, Age=30,
            )


# 5–8. API INTEGRATION

@pytest.fixture(scope="module")
def client():
    from main import app
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


def _login(client, username, password):
    r = client.post("/auth/login", json={"username": username, "password": password})
    return r.json().get("access_token")


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def admin_tok(client):
    return _login(client, "admin", "Admin@12345!")


@pytest.fixture(scope="module")
def doctor_tok(client):
    return _login(client, "dr_joseph", "Doctor@12345!")


@pytest.fixture(scope="module")
def nurse_tok(client):
    return _login(client, "nurse_patrick", "Nurse@12345!")


# 5. Auth

class TestAPIAuth:

    def test_self_register_success(self, client):
        r = client.post("/auth/register", json={
            "username": "new_user_test", "email": "new_test@hospital.com",
            "full_name": "New Test User",  "password": "NewUser@123!",
        })
        assert r.status_code == 201
        assert "pending" in r.json()["message"].lower()

    def test_self_register_duplicate_rejected(self, client):
        r = client.post("/auth/register", json={
            "username": "new_user_test", "email": "new_test@hospital.com",
            "full_name": "Duplicate",      "password": "NewUser@123!",
        })
        assert r.status_code == 400

    def test_pending_user_cannot_login(self, client):
        """Newly registered user is blocked until admin assigns a role."""
        r = client.post("/auth/login", json={
            "username": "new_user_test", "password": "NewUser@123!"
        })
        assert r.status_code == 403
        assert "pending" in r.json()["detail"].lower()

    def test_admin_login_success(self, client):
        r = client.post("/auth/login", json={"username": "admin", "password": "Admin@12345!"})
        assert r.status_code == 200
        assert "access_token" in r.json()

    def test_login_wrong_password(self, client):
        r = client.post("/auth/login", json={"username": "admin", "password": "wrong!"})
        assert r.status_code == 401

    def test_me_endpoint(self, client, admin_tok):
        r = client.get("/auth/me", headers=_auth(admin_tok))
        assert r.status_code == 200
        assert r.json()["username"] == "admin"

    def test_me_without_token(self, client):
        assert client.get("/auth/me").status_code == 401

    def test_weak_password_rejected(self, client):
        r = client.post("/auth/register", json={
            "username": "weakpass", "email": "weak@test.com",
            "full_name": "Weak Pass",  "password": "abc",
        })
        assert r.status_code == 400


# 6. Federated

class TestAPIFederated:

    def test_dataset_info(self, client, admin_tok):
        r = client.get("/federated/dataset-info", headers=_auth(admin_tok))
        assert r.status_code == 200
        assert "diabetes" in r.json()

    def test_status_accessible_to_all(self, client, nurse_tok):
        r = client.get("/federated/status", headers=_auth(nurse_tok))
        assert r.status_code == 200

    def test_predict_requires_auth(self, client):
        r = client.post("/federated/predict/diabetes", json={
            "Pregnancies": 1, "Glucose": 120, "BloodPressure": 70,
            "SkinThickness": 20, "Insulin": 80, "BMI": 25.0,
            "DiabetesPedigreeFunction": 0.5, "Age": 30,
        })
        assert r.status_code == 401

    def test_predict_nurse_is_forbidden(self, client, nurse_tok):
        """Nurses cannot run predictions — doctors and admins only."""
        r = client.post("/federated/predict/diabetes", json={
            "Pregnancies": 1, "Glucose": 120, "BloodPressure": 70,
            "SkinThickness": 20, "Insulin": 80, "BMI": 25.0,
            "DiabetesPedigreeFunction": 0.5, "Age": 30,
        }, headers=_auth(nurse_tok))
        assert r.status_code == 403


# 7. Admin

class TestAPIAdmin:

    def test_list_users_admin_only(self, client, admin_tok, doctor_tok):
        assert client.get("/admin/users", headers=_auth(admin_tok)).status_code  == 200
        assert client.get("/admin/users", headers=_auth(doctor_tok)).status_code == 403

    def test_pending_users_list(self, client, admin_tok):
        r = client.get("/admin/users/pending", headers=_auth(admin_tok))
        assert r.status_code == 200
        data = r.json()
        assert "pending_users" in data
        # new_user_test from TestAPIAuth should be in here
        usernames = [u["username"] for u in data["pending_users"]]
        assert "new_user_test" in usernames

    def test_assign_role_approves_account(self, client, admin_tok):
        """Admin assigns doctor role → user can now log in."""
        # Get the user_id of new_user_test
        users_r = client.get("/admin/users", headers=_auth(admin_tok))
        user_id = next(u["id"] for u in users_r.json() if u["username"] == "new_user_test")

        # Assign role
        r = client.put(f"/admin/users/{user_id}/role",
                       json={"role": "nurse"}, headers=_auth(admin_tok))
        assert r.status_code == 200
        assert r.json()["is_approved"] is True

        # Now the user can log in
        login_r = client.post("/auth/login", json={
            "username": "new_user_test", "password": "NewUser@123!"
        })
        assert login_r.status_code == 200
        assert "access_token" in login_r.json()

    def test_invalid_role_rejected(self, client, admin_tok):
        users_r = client.get("/admin/users", headers=_auth(admin_tok))
        user_id = users_r.json()[0]["id"]
        r = client.put(f"/admin/users/{user_id}/role",
                       json={"role": "superadmin"}, headers=_auth(admin_tok))
        assert r.status_code == 400

    def test_audit_logs_paginated(self, client, admin_tok):
        r = client.get("/admin/audit-logs?page=1&page_size=10", headers=_auth(admin_tok))
        assert r.status_code == 200
        assert "logs" in r.json()

    def test_dashboard_stats(self, client, admin_tok):
        r = client.get("/admin/dashboard-stats", headers=_auth(admin_tok))
        assert r.status_code == 200
        d = r.json()
        assert "users" in d and "pending" in d["users"]
        assert "predictions" in d
        assert "security" in d


# 8. Security Training

class TestAPITraining:

    def test_training_status(self, client, admin_tok):
        r = client.get("/training/status", headers=_auth(admin_tok))
        assert r.status_code == 200
        assert "is_current" in r.json()

    def test_complete_training_pass(self, client, admin_tok):
        r = client.post("/training/complete", json={
            "score": 5,
            "answers": {"q1": "a", "q2": "b", "q3": "c", "q4": "d", "q5": "e"},
        }, headers=_auth(admin_tok))
        assert r.status_code == 200
        assert r.json()["passed"] is True

    def test_complete_training_fail(self, client, nurse_tok):
        r = client.post("/training/complete", json={
            "score": 2,
            "answers": {"q1": "x", "q2": "x", "q3": "x", "q4": "x", "q5": "x"},
        }, headers=_auth(nurse_tok))
        assert r.status_code == 200
        assert r.json()["passed"] is False

    def test_training_unauthenticated_rejected(self, client):
        r = client.post("/training/complete", json={"score": 5, "answers": {}})
        assert r.status_code == 401