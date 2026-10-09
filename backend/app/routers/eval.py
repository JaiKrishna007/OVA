"""
Evaluation Router: Exposes clinical AI evaluation metrics and benchmark dashboard endpoints.
GET /eval/latest: returns latest evaluation run results (admin, doctor).
POST /eval/run: executes on-demand benchmark evaluation run.
"""

from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, desc

from app.db.session import get_db
from app.models.eval_run import EvalRun
from app.models.user import User
from app.models.enums import UserRole
from app.core.scope import require_roles, get_current_user
from app.core.audit import record_audit
from app.eval.run_eval import run_evaluation, EVAL_LATEST_JSON
import json

router = APIRouter(prefix="/eval", tags=["evaluation"])


@router.get(
    "/latest",
    summary="Get latest AI evaluation benchmark results",
    description="Returns the latest evaluation benchmark run across seed patients, including fact recall, citation accuracy, conflict recall, and validator degradation statistics. Accessible to doctors and admins.",
)
async def get_latest_eval_results(
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.DOCTOR)),
    db: Session = Depends(get_db),
):
    """
    Returns latest benchmark run. If none exists, automatically generates a fresh run.
    """
    latest_run = db.scalars(
        select(EvalRun).order_by(desc(EvalRun.run_at))
    ).first()

    if latest_run and latest_run.metrics_json:
        return latest_run.metrics_json

    # Check fallback JSON file
    if EVAL_LATEST_JSON.exists():
        try:
            with open(EVAL_LATEST_JSON, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    # If no run recorded, execute one
    results = run_evaluation(db=db, adversarial=False)
    return results


@router.post(
    "/run",
    summary="Trigger on-demand AI benchmark evaluation",
    description="Executes full benchmark evaluation across all seed patients, optionally with adversarial corruption.",
)
async def trigger_eval_run(
    adversarial: bool = Query(False, description="Enable adversarial claim corruption (60% corrupted claims)"),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.DOCTOR)),
    db: Session = Depends(get_db),
):
    """
    Executes a fresh evaluation benchmark run and returns computed results.
    Audit-logs the benchmark invocation.
    """
    record_audit(
        db,
        user_id=current_user.id,
        action="eval_run",
    )
    results = run_evaluation(db=db, adversarial=adversarial)
    return results
