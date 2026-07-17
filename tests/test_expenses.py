import uuid

from httpx import AsyncClient
from sqlalchemy import select

from app.models import Role, User
from tests.conftest import FakeStorage, auth, register_and_login

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


async def test_bola_and_mass_assignment_are_blocked(client: AsyncClient) -> None:
    user_a, token_a = await register_and_login(client, "a@example.com")
    _, token_b = await register_and_login(client, "b@example.com")
    created = await client.post(
        "/v1/expenses",
        headers=auth(token_a),
        json={"description": "Conference", "amount": "199.99", "currency": "usd"},
    )
    assert created.status_code == 201
    expense_id = created.json()["id"]
    assert created.json()["owner_id"] == user_a["id"]
    assert (
        await client.get(f"/v1/expenses/{expense_id}", headers=auth(token_b))
    ).status_code == 404

    attempt = await client.patch(
        f"/v1/expenses/{expense_id}",
        headers=auth(token_a),
        json={"owner_id": str(uuid.uuid4()), "state": "approved", "description": "Updated"},
    )
    assert attempt.status_code == 200
    assert attempt.json()["owner_id"] == user_a["id"]
    assert attempt.json()["state"] == "draft"


async def test_receipt_upload_submit_and_admin_approval(
    client: AsyncClient, test_context: dict[str, object]
) -> None:
    _, user_token = await register_and_login(client, "employee@example.com")
    admin_data, _ = await register_and_login(client, "admin@example.com")
    factory = test_context["factory"]
    async with factory() as db:  # type: ignore[operator]
        admin = await db.scalar(select(User).where(User.id == uuid.UUID(admin_data["id"])))
        assert admin is not None
        admin.role = Role.ADMIN
        await db.commit()
    admin_login = await client.post(
        "/v1/auth/login",
        json={"email": "admin@example.com", "password": "correct horse battery"},
    )
    admin_token = admin_login.json()["access_token"]

    created = await client.post(
        "/v1/expenses",
        headers=auth(user_token),
        json={"description": "Travel", "amount": "42.00", "currency": "PKR"},
    )
    expense_id = created.json()["id"]
    missing_receipt = await client.post(
        f"/v1/expenses/{expense_id}/submit", headers=auth(user_token)
    )
    assert missing_receipt.status_code == 409

    uploaded = await client.post(
        f"/v1/expenses/{expense_id}/receipt",
        headers=auth(user_token),
        files={"upload": ("../../invoice.png", PNG, "text/plain")},
    )
    assert uploaded.status_code == 200, uploaded.text
    storage = test_context["storage"]
    assert isinstance(storage, FakeStorage)
    object_key = next(iter(storage.objects))
    assert "invoice" not in object_key and ".." not in object_key

    submitted = await client.post(f"/v1/expenses/{expense_id}/submit", headers=auth(user_token))
    assert submitted.status_code == 200
    assert submitted.json()["state"] == "submitted"
    immutable = await client.patch(
        f"/v1/expenses/{expense_id}",
        headers=auth(user_token),
        json={"description": "Changed"},
    )
    assert immutable.status_code == 409

    approved = await client.post(
        f"/v1/admin/expenses/{expense_id}/approve",
        headers=auth(admin_token),
        json={"reason": "Policy compliant"},
    )
    assert approved.status_code == 200
    assert approved.json()["state"] == "approved"
    repeated = await client.post(
        f"/v1/admin/expenses/{expense_id}/approve",
        headers=auth(admin_token),
        json={},
    )
    assert repeated.status_code == 409

    download = await client.post(
        f"/v1/expenses/{expense_id}/receipt-download-url", headers=auth(user_token)
    )
    assert download.status_code == 200
    assert download.json()["expires_in"] == 60


async def test_upload_rejects_unrecognized_content(client: AsyncClient) -> None:
    _, token = await register_and_login(client, "files@example.com")
    created = await client.post(
        "/v1/expenses",
        headers=auth(token),
        json={"description": "Bad receipt", "amount": "1.00", "currency": "USD"},
    )
    response = await client.post(
        f"/v1/expenses/{created.json()['id']}/receipt",
        headers=auth(token),
        files={"upload": ("receipt.pdf", b"not really a pdf", "application/pdf")},
    )
    assert response.status_code == 415

    empty = await client.post(
        f"/v1/expenses/{created.json()['id']}/receipt",
        headers=auth(token),
        files={"upload": ("receipt.png", b"", "image/png")},
    )
    assert empty.status_code == 422


async def test_expense_listing_and_missing_receipt(client: AsyncClient) -> None:
    _, token = await register_and_login(client, "listing@example.com")
    created = await client.post(
        "/v1/expenses",
        headers=auth(token),
        json={"description": "Listed", "amount": "2.00", "currency": "EUR"},
    )
    listed = await client.get("/v1/expenses?offset=0&limit=1", headers=auth(token))
    assert listed.status_code == 200
    assert listed.json()[0]["id"] == created.json()["id"]
    missing = await client.post(
        f"/v1/expenses/{created.json()['id']}/receipt-download-url", headers=auth(token)
    )
    assert missing.status_code == 404


async def test_non_admin_cannot_access_admin_api(client: AsyncClient) -> None:
    _, token = await register_and_login(client, "normal@example.com")
    response = await client.get("/v1/admin/users", headers=auth(token))
    assert response.status_code == 403
