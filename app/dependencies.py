import uuid
from datetime import timedelta
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models import Role, Session, User
from app.security import ensure_utc, hash_token, utcnow

bearer = HTTPBearer(auto_error=False)
DbSession = Annotated[AsyncSession, Depends(get_db)]


async def get_current_session(
    request: Request,
    db: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> Session:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "authentication_required", "message": "Authentication required"},
        )
    session = await db.scalar(
        select(Session).where(Session.token_hash == hash_token(credentials.credentials))
    )
    now = utcnow()
    settings = get_settings()
    if (
        session is None
        or session.revoked_at is not None
        or ensure_utc(session.absolute_expires_at) <= now
        or ensure_utc(session.last_used_at)
        + timedelta(minutes=settings.session_idle_minutes)
        <= now
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "invalid_session", "message": "Session is invalid or expired"},
        )
    session.last_used_at = now
    request.state.session = session
    return session


async def get_current_user(
    db: DbSession, session: Annotated[Session, Depends(get_current_session)]
) -> User:
    user = await db.get(User, session.user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "inactive_user", "message": "Account is unavailable"},
        )
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentSession = Annotated[Session, Depends(get_current_session)]


async def require_admin(user: CurrentUser) -> User:
    if user.role is not Role.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "admin_required", "message": "Administrator role required"},
        )
    return user


AdminUser = Annotated[User, Depends(require_admin)]


def request_context(request: Request) -> tuple[str | None, str | None]:
    request_id = getattr(request.state, "request_id", None)
    source_ip = request.client.host if request.client else None
    return request_id, source_ip


def parse_uuid(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=404, detail={"code": "not_found", "message": "Resource not found"}
        ) from exc
