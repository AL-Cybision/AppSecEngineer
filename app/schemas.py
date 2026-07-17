import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models import ExpenseState, Role


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return str(value).strip().lower()


class LoginRequest(UserCreate):
    pass


class ResetRequest(BaseModel):
    email: EmailStr


class ResetConfirm(BaseModel):
    token: str = Field(min_length=32, max_length=256)
    new_password: str = Field(min_length=12, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"  # noqa: S105 - OAuth token type, not a credential
    expires_at: datetime


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    role: Role
    is_active: bool
    created_at: datetime


class ProfileUpdate(BaseModel):
    email: EmailStr

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return str(value).strip().lower()


class ExpenseCreate(BaseModel):
    description: str = Field(min_length=1, max_length=500)
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    currency: str = Field(pattern=r"^[A-Za-z]{3}$")

    @field_validator("currency")
    @classmethod
    def uppercase_currency(cls, value: str) -> str:
        return value.upper()


class ExpenseUpdate(BaseModel):
    description: str | None = Field(default=None, min_length=1, max_length=500)
    amount: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    currency: str | None = Field(default=None, pattern=r"^[A-Za-z]{3}$")

    @field_validator("currency")
    @classmethod
    def uppercase_currency(cls, value: str | None) -> str | None:
        return value.upper() if value else None


class ReceiptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    original_filename: str
    media_type: str
    size_bytes: int
    sha256: str
    created_at: datetime


class ExpenseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    owner_id: uuid.UUID
    description: str
    amount: Decimal
    currency: str
    state: ExpenseState
    decision_reason: str | None
    created_at: datetime
    updated_at: datetime
    receipt: ReceiptResponse | None = None


class DecisionRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class UserStatusUpdate(BaseModel):
    is_active: bool


class DownloadUrlResponse(BaseModel):
    url: str
    expires_in: int


class AuditEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    occurred_at: datetime
    actor_id: uuid.UUID | None
    action: str
    target_type: str | None
    target_id: str | None
    outcome: str
    request_id: str | None
    source_ip: str | None
    details: dict[str, object]


class Problem(BaseModel):
    type: str = "about:blank"
    title: str
    status: int
    detail: str
    code: str
    request_id: str | None = None
