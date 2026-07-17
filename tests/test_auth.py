from httpx import AsyncClient

from tests.conftest import FakeEmailSender, auth, register_and_login


async def test_registration_login_profile_and_logout(client: AsyncClient) -> None:
    response = await client.post(
        "/v1/auth/register",
        json={"email": "USER@Example.COM", "password": "correct horse battery"},
    )
    assert response.status_code == 201
    assert response.json()["email"] == "user@example.com"
    assert "password" not in response.text

    login = await client.post(
        "/v1/auth/login",
        json={"email": "user@example.com", "password": "correct horse battery"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]
    profile = await client.get("/v1/profile", headers=auth(token))
    assert profile.status_code == 200
    assert profile.headers["x-content-type-options"] == "nosniff"

    logout = await client.post("/v1/auth/logout", headers=auth(token))
    assert logout.status_code == 204
    assert (await client.get("/v1/profile", headers=auth(token))).status_code == 401


async def test_login_error_is_generic(client: AsyncClient) -> None:
    await register_and_login(client, "known@example.com")
    unknown = await client.post(
        "/v1/auth/login", json={"email": "unknown@example.com", "password": "incorrect password"}
    )
    wrong = await client.post(
        "/v1/auth/login", json={"email": "known@example.com", "password": "incorrect password"}
    )
    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json()["code"] == wrong.json()["code"] == "invalid_credentials"


async def test_password_reset_is_generic_and_revokes_sessions(
    client: AsyncClient, test_context: dict[str, object]
) -> None:
    _, old_token = await register_and_login(client, "reset@example.com")
    unknown = await client.post(
        "/v1/auth/password-reset/request", json={"email": "unknown@example.com"}
    )
    known = await client.post(
        "/v1/auth/password-reset/request", json={"email": "reset@example.com"}
    )
    assert unknown.status_code == known.status_code == 202
    assert unknown.json() == known.json()
    email = test_context["email"]
    assert isinstance(email, FakeEmailSender)
    recipient, reset_token = email.messages[-1]
    assert recipient == "reset@example.com"

    confirmed = await client.post(
        "/v1/auth/password-reset/confirm",
        json={"token": reset_token, "new_password": "a new correct battery"},
    )
    assert confirmed.status_code == 204
    assert (await client.get("/v1/profile", headers=auth(old_token))).status_code == 401
    replay = await client.post(
        "/v1/auth/password-reset/confirm",
        json={"token": reset_token, "new_password": "another correct battery"},
    )
    assert replay.status_code == 400
    new_login = await client.post(
        "/v1/auth/login",
        json={"email": "reset@example.com", "password": "a new correct battery"},
    )
    assert new_login.status_code == 200


async def test_registration_rate_limit(client: AsyncClient) -> None:
    for index in range(5):
        response = await client.post(
            "/v1/auth/register",
            json={"email": f"user{index}@example.com", "password": "correct horse battery"},
        )
        assert response.status_code == 201
    limited = await client.post(
        "/v1/auth/register",
        json={"email": "user6@example.com", "password": "correct horse battery"},
    )
    assert limited.status_code == 429
    assert limited.headers["retry-after"] == "3600"
