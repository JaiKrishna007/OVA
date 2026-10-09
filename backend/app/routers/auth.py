from datetime import timedelta
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.schemas.user import UserRead
from app.core.security import verify_password, create_access_token, DEFAULT_ACCESS_TOKEN_EXPIRE_MINUTES
from app.core.errors import AppException
from app.core.scope import get_current_user
from app.services.audit_service import AuditService, AuditEvent, AuditOutcome

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserRead


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, db: Session = Depends(get_db)):
    """Authenticate user and return a 1-hour JWT access token."""
    user = db.scalar(select(User).where(User.username == req.username))
    if not user or not verify_password(req.password, user.password_hash):
        # Attempt to find user for failed-login audit (best-effort)
        attempted_user = db.scalar(select(User).where(User.username == req.username))
        if attempted_user:
            AuditService.log_from_user(
                db=db,
                user=attempted_user,
                event_type=AuditEvent.LOGIN,
                outcome=AuditOutcome.FAILURE,
                details={"reason": "INVALID_CREDENTIALS"},
            )
        raise AppException(
            status_code=401,
            code="INVALID_CREDENTIALS",
            message="Invalid username or password",
        )

    expires_delta = timedelta(minutes=DEFAULT_ACCESS_TOKEN_EXPIRE_MINUTES)
    token = create_access_token(
        data={"sub": user.username, "role": user.role.value, "org_id": user.org_id},
        expires_delta=expires_delta,
    )

    AuditService.log_from_user(
        db=db,
        user=user,
        event_type=AuditEvent.LOGIN,
        outcome=AuditOutcome.SUCCESS,
        details={"method": "password"},
    )

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=DEFAULT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserRead.model_validate(user),
    )


@router.post("/logout", status_code=204)
async def logout(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Record logout event (token invalidation is client-side for stateless JWT)."""
    AuditService.log_from_user(
        db=db,
        user=current_user,
        event_type=AuditEvent.LOGOUT,
        outcome=AuditOutcome.SUCCESS,
    )
    return None


@router.get("/me", response_model=UserRead)
async def get_me(current_user: User = Depends(get_current_user)):
    """Return profile of the currently authenticated user."""
    return UserRead.model_validate(current_user)
