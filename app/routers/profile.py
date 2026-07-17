from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy.exc import IntegrityError

from app.dependencies import CurrentUser, DbSession, request_context
from app.schemas import ProfileUpdate, UserResponse
from app.services import audit

router = APIRouter(prefix="/v1/profile", tags=["profile"])


@router.get("", response_model=UserResponse)
async def get_profile(user: CurrentUser) -> object:
    return user


@router.patch("", response_model=UserResponse)
async def update_profile(
    payload: ProfileUpdate, request: Request, db: DbSession, user: CurrentUser
) -> object:
    user.email = str(payload.email)
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
        action="profile.update",
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
