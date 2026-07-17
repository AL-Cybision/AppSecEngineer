import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from app.dependencies import AdminUser, DbSession, request_context
from app.models import AuditEvent, Expense, ExpenseState, Session, User
from app.schemas import (
    AuditEventResponse,
    DecisionRequest,
    ExpenseResponse,
    UserResponse,
    UserStatusUpdate,
)
from app.security import utcnow
from app.services import audit

router = APIRouter(prefix="/v1/admin", tags=["administration"])


@router.get("/users", response_model=list[UserResponse])
async def list_users(
    db: DbSession,
    _admin: AdminUser,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[User]:
    result = await db.scalars(
        select(User).order_by(User.created_at.desc()).offset(offset).limit(limit)
    )
    return list(result)


@router.patch("/users/{user_id}/status", response_model=UserResponse)
async def set_user_status(
    user_id: uuid.UUID,
    payload: UserStatusUpdate,
    request: Request,
    db: DbSession,
    admin: AdminUser,
) -> User:
    target = await db.get(User, user_id, with_for_update=True)
    if target is None:
        raise HTTPException(
            status_code=404, detail={"code": "not_found", "message": "User not found"}
        )
    if target.id == admin.id and not payload.is_active:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "self_deactivation",
                "message": "Administrators cannot deactivate themselves",
            },
        )
    target.is_active = payload.is_active
    if not payload.is_active:
        await db.execute(
            update(Session)
            .where(Session.user_id == target.id, Session.revoked_at.is_(None))
            .values(revoked_at=utcnow())
        )
    request_id, source_ip = request_context(request)
    await audit(
        db,
        action="admin.user_status",
        outcome="success",
        actor_id=admin.id,
        target_type="user",
        target_id=str(target.id),
        request_id=request_id,
        source_ip=source_ip,
        details={"is_active": payload.is_active},
    )
    await db.commit()
    await db.refresh(target)
    return target


@router.get("/expenses", response_model=list[ExpenseResponse])
async def list_all_expenses(
    db: DbSession,
    _admin: AdminUser,
    state: ExpenseState | None = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[Expense]:
    stmt = (
        select(Expense).options(selectinload(Expense.receipt)).order_by(Expense.created_at.desc())
    )
    if state:
        stmt = stmt.where(Expense.state == state)
    result = await db.scalars(stmt.offset(offset).limit(limit))
    return list(result.unique())


async def decide(
    expense_id: uuid.UUID,
    payload: DecisionRequest,
    request: Request,
    db: DbSession,
    admin: User,
    new_state: ExpenseState,
) -> Expense:
    expense = await db.scalar(select(Expense).where(Expense.id == expense_id).with_for_update())
    if expense is None:
        raise HTTPException(
            status_code=404, detail={"code": "not_found", "message": "Expense not found"}
        )
    if expense.state is not ExpenseState.SUBMITTED:
        raise HTTPException(
            status_code=409,
            detail={"code": "invalid_state", "message": "Only submitted expenses can be decided"},
        )
    expense.state = new_state
    expense.decision_reason = payload.reason
    request_id, source_ip = request_context(request)
    await audit(
        db,
        action=f"expense.{new_state.value}",
        outcome="success",
        actor_id=admin.id,
        target_type="expense",
        target_id=str(expense.id),
        request_id=request_id,
        source_ip=source_ip,
        details={"reason": payload.reason} if payload.reason else {},
    )
    await db.commit()
    result = await db.scalar(
        select(Expense).options(selectinload(Expense.receipt)).where(Expense.id == expense.id)
    )
    assert result is not None
    return result


@router.post("/expenses/{expense_id}/approve", response_model=ExpenseResponse)
async def approve_expense(
    expense_id: uuid.UUID,
    payload: DecisionRequest,
    request: Request,
    db: DbSession,
    admin: AdminUser,
) -> Expense:
    return await decide(expense_id, payload, request, db, admin, ExpenseState.APPROVED)


@router.post("/expenses/{expense_id}/reject", response_model=ExpenseResponse)
async def reject_expense(
    expense_id: uuid.UUID,
    payload: DecisionRequest,
    request: Request,
    db: DbSession,
    admin: AdminUser,
) -> Expense:
    return await decide(expense_id, payload, request, db, admin, ExpenseState.REJECTED)


@router.get("/audit-events", response_model=list[AuditEventResponse])
async def list_audit_events(
    db: DbSession,
    _admin: AdminUser,
    action: str | None = None,
    outcome: str | None = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[AuditEvent]:
    stmt = select(AuditEvent).order_by(AuditEvent.occurred_at.desc())
    if action:
        stmt = stmt.where(AuditEvent.action == action)
    if outcome:
        stmt = stmt.where(AuditEvent.outcome == outcome)
    result = await db.scalars(stmt.offset(offset).limit(limit))
    return list(result)
