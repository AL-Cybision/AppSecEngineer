from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response, status
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from app.config import get_settings
from app.dependencies import CurrentSession, CurrentUser, DbSession, request_context
from app.models import PasswordResetToken, Role, Session, User
from app.schemas import (
    LoginRequest,
    ResetConfirm,
    ResetRequest,
    TokenResponse,
    UserCreate,
    UserResponse,
)
from app.security import generate_token, hash_password, hash_token, utcnow, verify_password
from app.services import EmailSender, audit, enforce_rate_limit, get_email_sender

router = APIRouter(prefix="/v1/auth", tags=["authentication"])
DUMMY_PASSWORD_HASH = hash_password("expenseguard timing equalization password")


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: UserCreate, request: Request, db: DbSession) -> User:
    _, source_ip = request_context(request)
    await enforce_rate_limit(
        db, action="register_ip", subject=source_ip or "unknown", limit=5, window=timedelta(hours=1)
    )
    user = User(
        email=str(payload.email), password_hash=hash_password(payload.password), role=Role.USER
    )
    db.add(user)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "email_unavailable", "message": "Email address is unavailable"},
        ) from exc
    request_id, source_ip = request_context(request)
    await audit(
        db,
        action="user.register",
        outcome="success",
        actor_id=user.id,
        target_type="user",
        target_id=str(user.id),
        request_id=request_id,
        source_ip=source_ip,
    )
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, request: Request, db: DbSession) -> TokenResponse:
    settings = get_settings()
    request_id, source_ip = request_context(request)
    subject = f"{payload.email}:{source_ip or 'unknown'}"
    await enforce_rate_limit(
        db, action="login_account_ip", subject=subject, limit=5, window=timedelta(minutes=15)
    )
    await enforce_rate_limit(
        db,
        action="login_ip",
        subject=source_ip or "unknown",
        limit=30,
        window=timedelta(minutes=15),
    )
    user = await db.scalar(select(User).where(User.email == str(payload.email)))
    candidate_hash = user.password_hash if user is not None else DUMMY_PASSWORD_HASH
    valid = verify_password(payload.password, candidate_hash)
    if not valid or user is None or not user.is_active:
        await audit(
            db,
            action="auth.login",
            outcome="failure",
            actor_id=user.id if user else None,
            request_id=request_id,
            source_ip=source_ip,
            details={"reason": "invalid_credentials"},
        )
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "invalid_credentials", "message": "Invalid email or password"},
        )
    now = utcnow()
    raw_token = generate_token()
    expires_at = now + timedelta(minutes=settings.session_absolute_minutes)
    session = Session(
        user_id=user.id,
        token_hash=hash_token(raw_token),
        last_used_at=now,
        absolute_expires_at=expires_at,
    )
    db.add(session)
    await db.flush()
    await audit(
        db,
        action="auth.login",
        outcome="success",
        actor_id=user.id,
        target_type="session",
        target_id=str(session.id),
        request_id=request_id,
        source_ip=source_ip,
    )
    await db.commit()
    return TokenResponse(access_token=raw_token, expires_at=expires_at)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request, db: DbSession, session: CurrentSession, user: CurrentUser
) -> Response:
    session.revoked_at = utcnow()
    request_id, source_ip = request_context(request)
    await audit(
        db,
        action="auth.logout",
        outcome="success",
        actor_id=user.id,
        target_type="session",
        target_id=str(session.id),
        request_id=request_id,
        source_ip=source_ip,
    )
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/password-reset/request", status_code=status.HTTP_202_ACCEPTED)
async def request_password_reset(
    payload: ResetRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: DbSession,
    sender: Annotated[EmailSender, Depends(get_email_sender)],
) -> dict[str, str]:
    settings = get_settings()
    request_id, source_ip = request_context(request)
    email = str(payload.email).lower()
    await enforce_rate_limit(
        db, action="reset_account", subject=email, limit=3, window=timedelta(hours=1)
    )
    await enforce_rate_limit(
        db, action="reset_ip", subject=source_ip or "unknown", limit=10, window=timedelta(hours=1)
    )
    user = await db.scalar(select(User).where(User.email == email, User.is_active.is_(True)))
    if user is not None:
        token = generate_token()
        db.add(
            PasswordResetToken(
                user_id=user.id,
                token_hash=hash_token(token),
                expires_at=utcnow() + timedelta(minutes=settings.reset_token_minutes),
            )
        )
        background_tasks.add_task(sender.send_password_reset, user.email, token)
    await audit(
        db,
        action="auth.password_reset_requested",
        outcome="accepted",
        actor_id=user.id if user else None,
        target_type="user",
        target_id=str(user.id) if user else None,
        request_id=request_id,
        source_ip=source_ip,
    )
    await db.commit()
    return {"message": "If the account exists, reset instructions will be sent"}


@router.post("/password-reset/confirm", status_code=status.HTTP_204_NO_CONTENT)
async def confirm_password_reset(
    payload: ResetConfirm, request: Request, db: DbSession
) -> Response:
    now = utcnow()
    reset = await db.scalar(
        select(PasswordResetToken)
        .where(
            PasswordResetToken.token_hash == hash_token(payload.token),
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.expires_at > now,
        )
        .with_for_update()
    )
    if reset is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_reset_token", "message": "Reset token is invalid or expired"},
        )
    user = await db.get(User, reset.user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_reset_token", "message": "Reset token is invalid or expired"},
        )
    user.password_hash = hash_password(payload.new_password)
    reset.used_at = now
    await db.execute(
        update(Session)
        .where(Session.user_id == user.id, Session.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    request_id, source_ip = request_context(request)
    await audit(
        db,
        action="auth.password_reset_completed",
        outcome="success",
        actor_id=user.id,
        target_type="user",
        target_id=str(user.id),
        request_id=request_id,
        source_ip=source_ip,
    )
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
