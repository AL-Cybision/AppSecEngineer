import uuid

from httpx import AsyncClient
from sqlalchemy import select

from app.models import Role, User
from tests.conftest import auth, register_and_login


async def promote(test_context: dict[str, object], user_id: str) -> None:
    factory = test_context["factory"]
    async with factory() as db:  # type: ignore[operator]
        user = await db.scalar(select(User).where(User.id == uuid.UUID(user_id)))
        assert user is not None
        user.role = Role.ADMIN
        await db.commit()


async def test_profile_update_and_duplicate_conflict(client: AsyncClient) -> None:
    _, first_token = await register_and_login(client, "first@example.com")
    await register_and_login(client, "second@example.com")
    updated = await client.patch(
        "/v1/profile", headers=auth(first_token), json={"email": "updated@example.com"}
    )
    assert updated.status_code == 200
    assert updated.json()["email"] == "updated@example.com"
    duplicate = await client.patch(
        "/v1/profile", headers=auth(first_token), json={"email": "second@example.com"}
    )
    assert duplicate.status_code == 409


async def test_admin_inventory_audit_and_deactivation(
    client: AsyncClient, test_context: dict[str, object]
) -> None:
    employee, employee_token = await register_and_login(client, "employee2@example.com")
    admin, _ = await register_and_login(client, "admin2@example.com")
    await promote(test_context, admin["id"])
    login = await client.post(
        "/v1/auth/login",
        json={"email": "admin2@example.com", "password": "correct horse battery"},
    )
    admin_token = login.json()["access_token"]

    users = await client.get("/v1/admin/users", headers=auth(admin_token))
    assert users.status_code == 200 and len(users.json()) == 2
    expenses = await client.get("/v1/admin/expenses?state=submitted", headers=auth(admin_token))
    assert expenses.status_code == 200 and expenses.json() == []
    events = await client.get(
        "/v1/admin/audit-events?action=auth.login&outcome=success", headers=auth(admin_token)
    )
    assert events.status_code == 200 and events.json()

    self_deactivate = await client.patch(
        f"/v1/admin/users/{admin['id']}/status",
        headers=auth(admin_token),
        json={"is_active": False},
    )
    assert self_deactivate.status_code == 409
    missing = await client.patch(
        f"/v1/admin/users/{uuid.uuid4()}/status",
        headers=auth(admin_token),
        json={"is_active": False},
    )
    assert missing.status_code == 404
    deactivated = await client.patch(
        f"/v1/admin/users/{employee['id']}/status",
        headers=auth(admin_token),
        json={"is_active": False},
    )
    assert deactivated.status_code == 200
    assert not deactivated.json()["is_active"]
    assert (await client.get("/v1/profile", headers=auth(employee_token))).status_code == 401


async def test_admin_rejects_submitted_expense(
    client: AsyncClient, test_context: dict[str, object]
) -> None:
    _, employee_token = await register_and_login(client, "reject@example.com")
    admin, _ = await register_and_login(client, "reject-admin@example.com")
    await promote(test_context, admin["id"])
    admin_login = await client.post(
        "/v1/auth/login",
        json={"email": "reject-admin@example.com", "password": "correct horse battery"},
    )
    admin_token = admin_login.json()["access_token"]
    created = await client.post(
        "/v1/expenses",
        headers=auth(employee_token),
        json={"description": "Reject me", "amount": "7.00", "currency": "USD"},
    )
    expense_id = created.json()["id"]
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
    assert (
        await client.post(
            f"/v1/expenses/{expense_id}/receipt",
            headers=auth(employee_token),
            files={"upload": ("receipt.png", png, "image/png")},
        )
    ).status_code == 200
    await client.post(f"/v1/expenses/{expense_id}/submit", headers=auth(employee_token))
    rejected = await client.post(
        f"/v1/admin/expenses/{expense_id}/reject",
        headers=auth(admin_token),
        json={"reason": "Outside policy"},
    )
    assert rejected.status_code == 200
    assert rejected.json()["state"] == "rejected"


async def test_validation_and_authentication_problem_responses(client: AsyncClient) -> None:
    health = await client.get("/health", headers={"Host": "10.40.10.25:8000"})
    assert health.status_code == 200
    rejected_host = await client.get("/docs", headers={"Host": "attacker.example"})
    assert rejected_host.status_code == 400
    unauthenticated = await client.get("/v1/profile")
    assert unauthenticated.status_code == 401
    assert unauthenticated.headers["content-type"].startswith("application/problem+json")
    invalid = await client.post("/v1/auth/register", json={"email": "invalid", "password": "short"})
    assert invalid.status_code == 422
    assert invalid.json()["code"] == "validation_failed"
