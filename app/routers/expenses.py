import uuid
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.dependencies import CurrentUser, DbSession, request_context
from app.models import Expense, ExpenseState, Receipt, Role
from app.schemas import (
    DownloadUrlResponse,
    ExpenseCreate,
    ExpenseResponse,
    ExpenseUpdate,
    ReceiptResponse,
)
from app.services import ObjectStorage, audit, get_storage, validate_and_spool_upload

router = APIRouter(prefix="/v1/expenses", tags=["expenses"])


def not_found() -> HTTPException:
    return HTTPException(
        status_code=404, detail={"code": "not_found", "message": "Expense not found"}
    )


async def visible_expense(db: DbSession, expense_id: uuid.UUID, user: CurrentUser) -> Expense:
    stmt = select(Expense).options(selectinload(Expense.receipt)).where(Expense.id == expense_id)
    if user.role is not Role.ADMIN:
        stmt = stmt.where(Expense.owner_id == user.id)
    expense = await db.scalar(stmt)
    if expense is None:
        raise not_found()
    return expense


@router.post("", response_model=ExpenseResponse, status_code=status.HTTP_201_CREATED)
async def create_expense(
    payload: ExpenseCreate, request: Request, db: DbSession, user: CurrentUser
) -> Expense:
    expense = Expense(owner_id=user.id, **payload.model_dump())
    db.add(expense)
    await db.flush()
    request_id, source_ip = request_context(request)
    await audit(
        db,
        action="expense.create",
        outcome="success",
        actor_id=user.id,
        target_type="expense",
        target_id=str(expense.id),
        request_id=request_id,
        source_ip=source_ip,
    )
    await db.commit()
    return await visible_expense(db, expense.id, user)


@router.get("", response_model=list[ExpenseResponse])
async def list_expenses(
    db: DbSession,
    user: CurrentUser,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[Expense]:
    stmt = (
        select(Expense).options(selectinload(Expense.receipt)).order_by(Expense.created_at.desc())
    )
    if user.role is not Role.ADMIN:
        stmt = stmt.where(Expense.owner_id == user.id)
    result = await db.scalars(stmt.offset(offset).limit(limit))
    return list(result.unique())


@router.get("/{expense_id}", response_model=ExpenseResponse)
async def get_expense(expense_id: uuid.UUID, db: DbSession, user: CurrentUser) -> Expense:
    return await visible_expense(db, expense_id, user)


@router.patch("/{expense_id}", response_model=ExpenseResponse)
async def update_expense(
    expense_id: uuid.UUID,
    payload: ExpenseUpdate,
    request: Request,
    db: DbSession,
    user: CurrentUser,
) -> Expense:
    expense = await visible_expense(db, expense_id, user)
    if expense.owner_id != user.id or expense.state is not ExpenseState.DRAFT:
        raise HTTPException(
            status_code=409,
            detail={"code": "invalid_state", "message": "Only the owner can edit a draft expense"},
        )
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(expense, field, value)
    request_id, source_ip = request_context(request)
    await audit(
        db,
        action="expense.update",
        outcome="success",
        actor_id=user.id,
        target_type="expense",
        target_id=str(expense.id),
        request_id=request_id,
        source_ip=source_ip,
    )
    await db.commit()
    return await visible_expense(db, expense.id, user)


@router.post("/{expense_id}/submit", response_model=ExpenseResponse)
async def submit_expense(
    expense_id: uuid.UUID, request: Request, db: DbSession, user: CurrentUser
) -> Expense:
    stmt = (
        select(Expense)
        .options(selectinload(Expense.receipt))
        .where(Expense.id == expense_id, Expense.owner_id == user.id)
        .with_for_update()
    )
    expense = await db.scalar(stmt)
    if expense is None:
        raise not_found()
    if expense.state is not ExpenseState.DRAFT:
        raise HTTPException(
            status_code=409,
            detail={"code": "invalid_state", "message": "Only draft expenses can be submitted"},
        )
    if expense.receipt is None:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "receipt_required",
                "message": "A receipt is required before submission",
            },
        )
    expense.state = ExpenseState.SUBMITTED
    request_id, source_ip = request_context(request)
    await audit(
        db,
        action="expense.submit",
        outcome="success",
        actor_id=user.id,
        target_type="expense",
        target_id=str(expense.id),
        request_id=request_id,
        source_ip=source_ip,
    )
    await db.commit()
    return await visible_expense(db, expense.id, user)


@router.post("/{expense_id}/receipt", response_model=ReceiptResponse)
async def upload_receipt(
    expense_id: uuid.UUID,
    request: Request,
    db: DbSession,
    user: CurrentUser,
    upload: Annotated[UploadFile, File()],
    storage: Annotated[ObjectStorage, Depends(get_storage)],
) -> Receipt:
    expense = await visible_expense(db, expense_id, user)
    if expense.owner_id != user.id or expense.state is not ExpenseState.DRAFT:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "invalid_state",
                "message": "Receipts can only be changed on owned draft expenses",
            },
        )
    temp, media_type, size, digest = await validate_and_spool_upload(upload)
    extension = {"application/pdf": "pdf", "image/jpeg": "jpg", "image/png": "png"}[media_type]
    object_key = f"receipts/{expense.id}/{uuid.uuid4()}.{extension}"
    old_key = expense.receipt.object_key if expense.receipt else None
    try:
        await storage.put(temp, object_key, media_type)
    finally:
        temp.close()
    safe_filename = Path(upload.filename or f"receipt.{extension}").name[:255]
    if expense.receipt:
        receipt = expense.receipt
        receipt.object_key = object_key
        receipt.original_filename = safe_filename
        receipt.media_type = media_type
        receipt.size_bytes = size
        receipt.sha256 = digest
    else:
        receipt = Receipt(
            expense_id=expense.id,
            object_key=object_key,
            original_filename=safe_filename,
            media_type=media_type,
            size_bytes=size,
            sha256=digest,
        )
        db.add(receipt)
    request_id, source_ip = request_context(request)
    await audit(
        db,
        action="receipt.upload",
        outcome="success",
        actor_id=user.id,
        target_type="expense",
        target_id=str(expense.id),
        request_id=request_id,
        source_ip=source_ip,
        details={"media_type": media_type, "size_bytes": size, "sha256": digest},
    )
    try:
        await db.commit()
    except Exception:
        await storage.delete(object_key)
        raise
    if old_key:
        await storage.delete(old_key)
    await db.refresh(receipt)
    return receipt


@router.post("/{expense_id}/receipt-download-url", response_model=DownloadUrlResponse)
async def receipt_download_url(
    expense_id: uuid.UUID,
    request: Request,
    db: DbSession,
    user: CurrentUser,
    storage: Annotated[ObjectStorage, Depends(get_storage)],
) -> DownloadUrlResponse:
    expense = await visible_expense(db, expense_id, user)
    if expense.receipt is None:
        raise HTTPException(
            status_code=404, detail={"code": "receipt_not_found", "message": "Receipt not found"}
        )
    url = await storage.presign_download(
        expense.receipt.object_key, expense.receipt.original_filename
    )
    request_id, source_ip = request_context(request)
    await audit(
        db,
        action="receipt.download_url",
        outcome="success",
        actor_id=user.id,
        target_type="expense",
        target_id=str(expense.id),
        request_id=request_id,
        source_ip=source_ip,
    )
    await db.commit()
    return DownloadUrlResponse(url=url, expires_in=get_settings().storage_presign_seconds)
