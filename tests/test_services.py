import io
from datetime import UTC, datetime
from typing import Any

from app.config import Settings
from app.security import ensure_utc
from app.services import S3ObjectStorage, SMTPEmailSender


class FakeS3Client:
    def __init__(self) -> None:
        self.uploaded = False
        self.upload_kwargs: dict[str, Any] = {}
        self.deleted = False

    def upload_fileobj(self, *_args: Any, **kwargs: Any) -> None:
        self.uploaded = True
        self.upload_kwargs = kwargs

    def delete_object(self, **_kwargs: Any) -> None:
        self.deleted = True

    def generate_presigned_url(self, *_args: Any, **_kwargs: Any) -> str:
        return "https://storage.example.test/signed"


async def test_s3_adapter_put_delete_and_presign(monkeypatch: Any) -> None:
    fake = FakeS3Client()
    monkeypatch.setattr("app.services.boto3.client", lambda *_args, **_kwargs: fake)
    storage = S3ObjectStorage(
        Settings(app_env="test", storage_bucket="receipts", storage_request_encryption=True)
    )
    await storage.put(io.BytesIO(b"pdf"), "receipts/id/file.pdf", "application/pdf")
    assert fake.uploaded
    assert fake.upload_kwargs["ExtraArgs"]["ServerSideEncryption"] == "AES256"
    assert await storage.presign_download("receipts/id/file.pdf", "../../safe.pdf") == (
        "https://storage.example.test/signed"
    )
    await storage.delete("receipts/id/file.pdf")
    assert fake.deleted


async def test_s3_adapter_can_defer_encryption_to_local_storage(monkeypatch: Any) -> None:
    fake = FakeS3Client()
    monkeypatch.setattr("app.services.boto3.client", lambda *_args, **_kwargs: fake)
    storage = S3ObjectStorage(
        Settings(app_env="test", storage_bucket="receipts", storage_request_encryption=False)
    )
    await storage.put(io.BytesIO(b"pdf"), "receipts/id/file.pdf", "application/pdf")
    assert fake.upload_kwargs["ExtraArgs"] == {"ContentType": "application/pdf"}


async def test_smtp_adapter_and_timezone_normalization(monkeypatch: Any) -> None:
    sent: list[object] = []

    class FakeSMTP:
        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            pass

        def __enter__(self) -> "FakeSMTP":
            return self

        def __exit__(self, *_args: Any) -> None:
            pass

        def send_message(self, message: object) -> None:
            sent.append(message)

    monkeypatch.setattr("app.services.smtplib.SMTP", FakeSMTP)
    sender = SMTPEmailSender(Settings(app_env="test"))
    await sender.send_password_reset("user@example.com", "synthetic-reset-token")
    assert len(sent) == 1
    naive = datetime(2026, 1, 1)
    assert ensure_utc(naive).tzinfo is UTC
    aware = datetime(2026, 1, 1, tzinfo=UTC)
    assert ensure_utc(aware) is aware
