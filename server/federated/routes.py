"""
Federated Learning endpoints:
  POST /federated/train        - start FL training in background thread
  GET  /federated/status       - poll training progress
  GET  /federated/metrics      - per-round metrics after training
  GET  /federated/dataset-info - dataset sizes, features (no raw data)
  POST /federated/predict/diabetes  - run diabetes prediction
  POST /federated/predict/heart     - run heart disease prediction
  GET  /federated/predictions  - history of predictions made by current user
"""

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.dependencies import get_current_user, require_admin, require_doctor, require_any
from database.models import AuditLog, PredictionLog, User
from database.base import get_db
from federated.server import (
    MODELS_DIR,
    read_fl_status,
    start_fl_training_background,
)
from ml.predict import (
    DiabetesInput,
    HeartInput,
    models_are_ready,
    predict_diabetes,
    predict_heart,
)
from ml.preprocess import get_dataset_stats

router = APIRouter(prefix="/federated", tags=["Federated Learning"])


async def _log_audit(db, action, request, user_id, resource=None, detail=None, success=True):
    log = AuditLog(
        user_id=user_id, action=action, resource=resource, detail=detail,
        ip_address=request.client.host if request.client else "unknown",
        user_agent=request.headers.get("user-agent", "")[:255],
        success=success,
    )
    db.add(log)
    await db.flush()


# Training

@router.post("/train")
async def start_training(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Admin only: start federated learning training in a background thread."""
    result = start_fl_training_background()
    await _log_audit(db, "FL_TRAINING_STARTED", request, current_user.id)
    return result


@router.get("/status")
async def training_status(current_user: User = Depends(require_any)):
    """Poll current federated training status and progress."""
    return read_fl_status()


@router.get("/metrics")
async def training_metrics(current_user: User = Depends(require_any)):
    """Return detailed per-round metrics after training is complete."""
    status = read_fl_status()
    if status.get("status") not in ("complete",):
        raise HTTPException(
            status_code=400,
            detail="Training has not completed yet. Check /federated/status.",
        )
    return status


@router.get("/dataset-info")
async def dataset_info(current_user: User = Depends(require_any)):
    """Return metadata about training/test datasets (no raw patient data)."""
    return get_dataset_stats()


# Predictions

@router.post("/predict/diabetes")
async def predict_diabetes_endpoint(
    data: DiabetesInput,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_doctor),
):
    """
    Run diabetes risk prediction.
    PRIVACY: Only anonymised clinical measurements are logged. No patient PII.
    Accessible to: admin, doctor.
    """
    if not models_are_ready():
        raise HTTPException(
            status_code=503,
            detail="Models are not trained yet. Admin must run POST /federated/train first.",
        )

    try:
        result = predict_diabetes(data)
    except Exception as e:
        await _log_audit(db, "PREDICT_DIABETES", request, current_user.id, success=False, detail=str(e))
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")

    # Log anonymised prediction (no PII)
    log = PredictionLog(
        user_id=current_user.id,
        disease_type="diabetes",
        input_features=data.model_dump(),     # only numeric clinical values
        prediction=result["prediction"],
        confidence=result["confidence"],
        model_version=result["model_version"],
    )
    db.add(log)
    await _log_audit(
        db, "PREDICT_DIABETES", request, current_user.id,
        detail=f"risk={result['risk_level']}"
    )

    return result


@router.post("/predict/heart")
async def predict_heart_endpoint(
    data: HeartInput,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_doctor),
):
    """
    Run heart disease risk prediction.
    Accessible to: admin, doctor.
    """
    if not models_are_ready():
        raise HTTPException(
            status_code=503,
            detail="Models are not trained yet. Admin must run POST /federated/train first.",
        )

    try:
        result = predict_heart(data)
    except Exception as e:
        await _log_audit(db, "PREDICT_HEART", request, current_user.id, success=False, detail=str(e))
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")

    log = PredictionLog(
        user_id=current_user.id,
        disease_type="heart",
        input_features=data.model_dump(),
        prediction=result["prediction"],
        confidence=result["confidence"],
        model_version=result["model_version"],
    )
    db.add(log)
    await _log_audit(
        db, "PREDICT_HEART", request, current_user.id,
        detail=f"risk={result['risk_level']}"
    )

    return result


@router.get("/predictions")
async def my_predictions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_any),
):
    """
    Return the current user's prediction history.
    Admins can see all predictions (for audit purposes).
    """
    if current_user.role == "admin":
        result = await db.execute(
            select(PredictionLog).order_by(PredictionLog.timestamp.desc()).limit(200)
        )
    else:
        result = await db.execute(
            select(PredictionLog)
            .where(PredictionLog.user_id == current_user.id)
            .order_by(PredictionLog.timestamp.desc())
            .limit(100)
        )
    logs = result.scalars().all()
    return [
        {
            "id": l.id,
            "disease_type": l.disease_type,
            "prediction": l.prediction,
            "confidence": l.confidence,
            "risk_level": _risk_label(l.confidence, l.prediction),
            "model_version": l.model_version,
            "timestamp": l.timestamp.isoformat(),
        }
        for l in logs
    ]


def _risk_label(confidence: float, prediction: int) -> str:
    if prediction == 0:
        return "Low Risk"
    if confidence < 0.65:
        return "Moderate Risk"
    return "High Risk"