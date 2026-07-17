import os
from collections.abc import AsyncIterator
from typing import IO

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite://"
os.environ["TRUSTED_HOSTS"] = "testserver,localhost,127.0.0.1"

from app.database import Base, get_db  # noqa: E402
from app.main import create_app  # noqa: E402
from app.services import EmailSender, ObjectStorage, get_email_sender, get_storage  # noqa: E402


class FakeStorage(ObjectStorage):
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    async def put(self, fileobj: IO[bytes], object_key: str, media_type: str) -> None:
        self.objects[object_key] = fileobj.read()

    async def delete(self, object_key: str) -> None:
        self.objects.pop(object_key, None)

    async def presign_download(self, object_key: str, filename: str) -> str:
        assert object_key in self.objects
        return f"https://storage.example.test/{object_key}?expires=60"


class FakeEmailSender(EmailSender):
    def __init__(self) -> None:
        self.messages: list[tuple[str, str]] = []

    async def send_password_reset(self, recipient: str, token: str) -> None:
        self.messages.append((recipient, token))


@pytest.fixture
async def test_context() -> AsyncIterator[dict[str, object]]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    storage = FakeStorage()
    email = FakeEmailSender()
    app = create_app()

    async def override_db() -> AsyncIterator[object]:
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_storage] = lambda: storage
    app.dependency_overrides[get_email_sender] = lambda: email
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        yield {"client": client, "factory": factory, "storage": storage, "email": email}
    await engine.dispose()


@pytest.fixture
def client(test_context: dict[str, object]) -> AsyncClient:
    return test_context["client"]  # type: ignore[return-value]


async def register_and_login(
    client: AsyncClient,
    email: str,
    password: str = "correct horse battery",  # noqa: S107 - synthetic fixture
) -> tuple[dict[str, object], str]:
    registered = await client.post("/v1/auth/register", json={"email": email, "password": password})
    assert registered.status_code == 201, registered.text
    logged_in = await client.post("/v1/auth/login", json={"email": email, "password": password})
    assert logged_in.status_code == 200, logged_in.text
    return registered.json(), logged_in.json()["access_token"]


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
