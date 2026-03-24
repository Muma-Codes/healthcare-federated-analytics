"""
Admin and Security-Training endpoints

ADMIN (role=admin only):
  GET    /admin/users                - list all users including pending
  GET    /admin/users/pending        - list only pending-approval accounts
  PUT    /admin/users/{id}/role      - assign role AND approve the account
  PUT    /admin/users/{id}/unlock    - unlock a locked account
  DELETE /admin/users/{id}           - deactivate an account
  GET    /admin/audit-logs           - paginated audit trail
  GET    /admin/dashboard-stats      - summary counts

SECURITY TRAINING (all authenticated roles):
  POST   /training/complete          - submit quiz result
  GET    /training/status            - check if current user is training-compliant
"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from auth.dependencies import get_current_user, require_admin, require_any
from database.base import get_db
from database.models import AuditLog, PredictionLog, TrainingCompletion, User

admin_router = APIRouter(prefix="/admin", tags=["Admin"])
training_router = APIRouter(prefix="/training", tags=["Security Training"])


# Shared audit helper

async def _log(db, action, request, admin_id, resource=None, detail=None, success=True):
    db.add(AuditLog(
        user_id=admin_id, action=action, resource=resource, detail=detail,
        ip_address=request.client.host if request.client else "unknown",
        success=success,
    ))
    await db.flush()


# Schemas

class RoleAssignment(BaseModel):
    role: str   # admin | doctor | nurse


# Admin: User Management

@admin_router.get("/users")
async def list_users(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """Return all users. Pending users show is_approved=False."""
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    users = result.scalars().all()
    return [_user_dict(u) for u in users]


@admin_router.get("/users/pending")
async def list_pending_users(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """Return only accounts awaiting role assignment."""
    result = await db.execute(
        select(User)
        .where(User.role == "pending")
        .order_by(User.created_at.desc())
    )
    users = result.scalars().all()
    return {
        "count": len(users),
        "pending_users": [_user_dict(u) for u in users],
    }


@admin_router.put("/users/{user_id}/role")
async def assign_role(
    user_id: int,
    payload: RoleAssignment,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """
    Assign a role to a user. This also approves the account.

    This is the ONLY way a pending user gets access:
      1. User registers (role=pending, is_approved=False)
      2. Admin calls this endpoint with role=doctor|nurse|admin
      3. is_approved becomes True and the user can now log in

    Also used to change roles of existing approved users.
    """
    if payload.role not in ("admin", "doctor", "nurse"):
        raise HTTPException(status_code=400, detail="Role must be admin, doctor or nurse.")

    result = await db.execute(select(User).where(User.id == user_id))
    user: User | None = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    previous_role = user.role
    user.role = payload.role
    user.is_approved = True         # <- approves the account
    user.is_active = True

    await _log(
        db, "ROLE_UPDATED", request, _admin.id,
        resource=f"users/{user_id}",
        detail=f"role: {previous_role} -> {payload.role}; approved=True",
    )

    action_word = "approved and assigned" if previous_role == "pending" else "updated to"
    return {
        "message": f"User '{user.username}' {action_word} role '{payload.role}'. They can now log in.",
        "user_id": user.id,
        "role": user.role,
        "is_approved": user.is_approved,
    }


@admin_router.put("/users/{user_id}/unlock")
async def unlock_user(
    user_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user: User | None = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    user.is_locked             = False
    user.failed_login_attempts = 0
    user.locked_until          = None
    await _log(db, "USER_UNLOCKED", request, _admin.id, f"users/{user_id}")
    return {"message": f"User '{user.username}' has been unlocked."}


@admin_router.delete("/users/{user_id}")
async def deactivate_user(
    user_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    if user_id == _admin.id:
        raise HTTPException(status_code=400, detail="You cannot deactivate your own account.")
    result = await db.execute(select(User).where(User.id == user_id))
    user: User | None = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    user.is_active = False
    await _log(db, "USER_DEACTIVATED", request, _admin.id, f"users/{user_id}")
    return {"message": f"User '{user.username}' has been deactivated."}


# Admin: Audit Logs

@admin_router.get("/audit-logs")
async def get_audit_logs(
    page: int = 1,
    page_size: int = 50,
    action_filter: str | None = None,
    user_id_filter: int | None = None,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    offset = (page - 1) * page_size
    query = select(AuditLog).order_by(AuditLog.timestamp.desc())
    if action_filter:
        query = query.where(AuditLog.action.ilike(f"%{action_filter}%"))
    if user_id_filter:
        query = query.where(AuditLog.user_id == user_id_filter)

    count_q = select(func.count()).select_from(AuditLog)
    if action_filter:
        count_q = count_q.where(AuditLog.action.ilike(f"%{action_filter}%"))
    total = (await db.execute(count_q)).scalar()
    result = await db.execute(query.offset(offset).limit(page_size))
    logs = result.scalars().all()

    return {
        "total": total,
        "page": page,
        "pages": max(1, (total + page_size - 1) // page_size),
        "logs": [
            {
                "id": l.id, "user_id": l.user_id, "action": l.action,
                "resource": l.resource, "detail": l.detail,
                "ip_address": l.ip_address, "success": l.success,
                "timestamp": l.timestamp.isoformat(),
            }
            for l in logs
        ],
    }


# Admin: Dashboard Stats

@admin_router.get("/dashboard-stats")
async def dashboard_stats(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_any),
):
    total_users = (await db.execute(select(func.count()).select_from(User))).scalar()
    active_users = (await db.execute(
        select(func.count()).select_from(User).where(User.is_active == True)
    )).scalar()
    pending_users = (await db.execute(
        select(func.count()).select_from(User).where(User.role == "pending")
    )).scalar()
    locked_users = (await db.execute(
        select(func.count()).select_from(User).where(User.is_locked == True)
    )).scalar()
    total_preds = (await db.execute(select(func.count()).select_from(PredictionLog))).scalar()

    today = datetime.now(timezone.utc).date()
    today_preds = (await db.execute(
        select(func.count()).select_from(PredictionLog)
        .where(func.date(PredictionLog.timestamp) == today)
    )).scalar()
    failed_logins = (await db.execute(
        select(func.count()).select_from(AuditLog)
        .where(AuditLog.action == "LOGIN_FAIL", func.date(AuditLog.timestamp) == today)
    )).scalar()

    cutoff = datetime.now(timezone.utc) - timedelta(days=365)
    trained = (await db.execute(
        select(func.count()).select_from(User)
        .where(User.last_training_date >= cutoff, User.is_active == True)
    )).scalar()

    return {
        "users": {
            "total": total_users,
            "active": active_users,
            "pending": pending_users,
            "locked": locked_users,
        },
        "predictions": {
            "total": total_preds,
            "today": today_preds,
        },
        "security": {
            "failed_logins_today": failed_logins,
            "training_compliant": trained,
            "training_non_compliant": active_users - trained,
        },
    }


# Security Training

class TrainingResult(BaseModel):
    score: int    # 0–5
    answers: dict


@training_router.post("/complete")
async def complete_training(
    payload: TrainingResult,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_any),
):
    passed = payload.score >= 4
    db.add(TrainingCompletion(user_id=current_user.id, score=payload.score, passed=passed))
    if passed:
        current_user.last_training_date = datetime.now(timezone.utc)
    db.add(AuditLog(
        user_id=current_user.id, action="TRAINING_COMPLETED",
        detail=f"score={payload.score}/5 passed={passed}",
        ip_address=request.client.host if request.client else "unknown",
        success=True,
    ))
    return {
        "passed": passed,
        "score": payload.score,
        "message": "Training passed! Your record has been updated." if passed
                   else "Score below 4/5. Please review the material and try again.",
    }


@training_router.get("/status")
async def training_status_check(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_any),
):
    if not current_user.last_training_date:
        return {"is_current": False, "days_since_training": None,
                "message": "No training on record. Please complete the security training module."}
    days_since = (datetime.now(timezone.utc) - current_user.last_training_date).days
    is_current = days_since <= 365
    return {
        "is_current": is_current,
        "days_since_training": days_since,
        "last_training_date": current_user.last_training_date.isoformat(),
        "message": "Training is current." if is_current
                   else f"Training expired. Please redo the security training module.",
    }


# Shared helper

def _user_dict(u: User) -> dict:
    return {
        "id": u.id, "username": u.username, "email": u.email,
        "full_name": u.full_name, "role": u.role,
        "is_active": u.is_active, "is_approved": u.is_approved,
        "is_locked": u.is_locked, "mfa_enabled": u.mfa_enabled,
        "must_change_password": u.must_change_password,
        "failed_login_attempts": u.failed_login_attempts,
        "last_login": u.last_login.isoformat() if u.last_login else None,
        "last_training_date": u.last_training_date.isoformat() if u.last_training_date else None,
        "created_at": u.created_at.isoformat(),
    }