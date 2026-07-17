import hashlib
import json
import logging
import smtplib
import tempfile
import uuid
from datetime import timedelta
from email.message import EmailMessage
from pathlib import Path
from typing import IO, Protocol

import boto3  # type: ignore[import-untyped]
import filetype  # type: ignore[import-untyped]
from anyio import to_thread
from fastapi import HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.models import AuditEvent, RateLimitEvent
from app.security import hash_rate_limit_subject, utcnow

logger = logging.getLogger("expenseguard.security")

MAX_RECEIPT_BYTES = 10 * 1024 * 1024
ALLOWED_MEDIA_TYPES = {
    "application/pdf": "pdf",
    "image/jpeg": "jpg",
    "image/png": "png",
}


async def audit(
    db: AsyncSession,
    *,
    action: str,
    outcome: str,
    actor_id: uuid.UUID | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    request_id: str | None = None,
    source_ip: str | None = None,
    details: dict[str, object] | None = None,
) -> None:
    safe_details = details or {}
    event = AuditEvent(
        actor_id=actor_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        outcome=outcome,
        request_id=request_id,
        source_ip=source_ip,
        details=safe_details,
    )
    db.add(event)
    logger.info(
        json.dumps(
            {
                "event": "security_event",
                "action": action,
                "outcome": outcome,
                "actor_id": str(actor_id) if actor_id else None,
                "target_type": target_type,
                "target_id": target_id,
                "request_id": request_id,
            }
        )
    )


async def enforce_rate_limit(
    db: AsyncSession,
    *,
    action: str,
    subject: str,
    limit: int,
    window: timedelta,
) -> None:
    subject_hash = hash_rate_limit_subject(subject)
    since = utcnow() - window
    count = await db.scalar(
        select(func.count(RateLimitEvent.id)).where(
            RateLimitEvent.action == action,
            RateLimitEvent.subject_hash == subject_hash,
            RateLimitEvent.occurred_at >= since,
        )
    )
    if count is not None and count >= limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"code": "rate_limited", "message": "Too many requests"},
            headers={"Retry-After": str(int(window.total_seconds()))},
        )
    db.add(RateLimitEvent(action=action, subject_hash=subject_hash, occurred_at=utcnow()))


class ObjectStorage(Protocol):
    async def put(self, fileobj: IO[bytes], object_key: str, media_type: str) -> None: ...

    async def delete(self, object_key: str) -> None: ...

    async def presign_download(self, object_key: str, filename: str) -> str: ...


class S3ObjectStorage:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        kwargs: dict[str, object] = {"region_name": self.settings.storage_region}
        if self.settings.storage_endpoint_url:
            kwargs["endpoint_url"] = self.settings.storage_endpoint_url
        if self.settings.storage_access_key and self.settings.storage_secret_key:
            kwargs["aws_access_key_id"] = self.settings.storage_access_key
            kwargs["aws_secret_access_key"] = self.settings.storage_secret_key
        self.client = boto3.client("s3", **kwargs)

    async def ensure_bucket(self) -> None:
        def ensure() -> None:
            try:
                self.client.head_bucket(Bucket=self.settings.storage_bucket)
            except self.client.exceptions.ClientError:
                self.client.create_bucket(Bucket=self.settings.storage_bucket)

        await to_thread.run_sync(ensure)

    async def put(self, fileobj: IO[bytes], object_key: str, media_type: str) -> None:
        extra_args = {"ContentType": media_type}
        if self.settings.storage_request_encryption:
            extra_args["ServerSideEncryption"] = "AES256"
        await to_thread.run_sync(
            lambda: self.client.upload_fileobj(
                fileobj,
                self.settings.storage_bucket,
                object_key,
                ExtraArgs=extra_args,
            )
        )

    async def delete(self, object_key: str) -> None:
        await to_thread.run_sync(
            lambda: self.client.delete_object(Bucket=self.settings.storage_bucket, Key=object_key)
        )

    async def presign_download(self, object_key: str, filename: str) -> str:
        safe_name = Path(filename).name.replace('"', "")[:200]
        return await to_thread.run_sync(
            lambda: self.client.generate_presigned_url(
                "get_object",
                Params={
                    "Bucket": self.settings.storage_bucket,
                    "Key": object_key,
                    "ResponseContentDisposition": f'attachment; filename="{safe_name}"',
                },
                ExpiresIn=self.settings.storage_presign_seconds,
            )
        )


async def validate_and_spool_upload(
    upload: UploadFile,
) -> tuple[tempfile.SpooledTemporaryFile[bytes], str, int, str]:
    suffix = Path(upload.filename or "receipt").suffix
    temp = tempfile.SpooledTemporaryFile(max_size=MAX_RECEIPT_BYTES, mode="w+b", suffix=suffix)
    digest = hashlib.sha256()
    total = 0
    header = bytearray()
    while chunk := await upload.read(64 * 1024):
        total += len(chunk)
        if total > MAX_RECEIPT_BYTES:
            temp.close()
            raise HTTPException(
                status_code=413,
                detail={"code": "file_too_large", "message": "Receipt exceeds 10 MiB"},
            )
        if len(header) < 8192:
            header.extend(chunk[: 8192 - len(header)])
        digest.update(chunk)
        temp.write(chunk)
    if total == 0:
        temp.close()
        raise HTTPException(
            status_code=422, detail={"code": "empty_file", "message": "Receipt is empty"}
        )
    kind = filetype.guess(bytes(header))
    media_type = str(kind.mime) if kind else ""
    if media_type not in ALLOWED_MEDIA_TYPES:
        temp.close()
        raise HTTPException(
            status_code=415,
            detail={
                "code": "unsupported_file",
                "message": "Only PDF, JPEG, and PNG receipts are allowed",
            },
        )
    temp.seek(0)
    return temp, media_type, total, digest.hexdigest()


class EmailSender(Protocol):
    async def send_password_reset(self, recipient: str, token: str) -> None: ...


class SMTPEmailSender:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    async def send_password_reset(self, recipient: str, token: str) -> None:
        message = EmailMessage()
        message["From"] = self.settings.smtp_from
        message["To"] = recipient
        message["Subject"] = "ExpenseGuard password reset"
        message.set_content(
            "Use this one-time token within 30 minutes via the password reset API:\n\n"
            f"{token}\n\nAPI documentation: {self.settings.public_reset_url}\n"
        )

        def send() -> None:
            with smtplib.SMTP(self.settings.smtp_host, self.settings.smtp_port, timeout=10) as smtp:
                smtp.send_message(message)

        await to_thread.run_sync(send)


def get_storage() -> ObjectStorage:
    return S3ObjectStorage()


def get_email_sender() -> EmailSender:
    return SMTPEmailSender()
