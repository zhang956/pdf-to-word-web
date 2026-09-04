import httpx
import pytest
from types import SimpleNamespace

import app.main as main_module
import app.auth as auth_module
from app.main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
        follow_redirects=False,
    ) as test_client:
        yield test_client


@pytest.mark.anyio
async def test_health_is_public_and_fixed(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.anyio
async def test_home_redirects_to_login_but_api_returns_json_401(client):
    home = await client.get("/")
    api = await client.get("/api/tasks/missing")

    assert home.status_code == 303
    assert home.headers["location"] == "/login"
    assert api.status_code == 401
    assert api.json()["detail"] == "请先登录"


@pytest.mark.anyio
async def test_correct_password_creates_session_and_logout_clears_it(client):
    response = await client.post(
        "/login",
        data={"password": "local-dev-password"},
        headers={"origin": "http://test"},
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/"
    cookie = response.headers["set-cookie"]
    assert "httponly" in cookie.lower()
    assert "samesite=lax" in cookie.lower()
    assert "local-dev-password" not in cookie
    assert (await client.get("/")).status_code == 200

    logout = await client.post("/logout", headers={"origin": "http://test"})
    assert logout.status_code == 303
    assert (await client.get("/")).status_code == 303


@pytest.mark.anyio
async def test_wrong_password_uses_generic_error(client):
    response = await client.post(
        "/login",
        data={"password": "wrong"},
        headers={"origin": "http://test"},
    )

    assert response.status_code == 401
    assert "密码错误，请重试" in response.text
    assert "wrong" not in response.text


@pytest.mark.anyio
async def test_cross_origin_login_is_rejected(client):
    response = await client.post(
        "/login",
        data={"password": "local-dev-password"},
        headers={"origin": "https://attacker.example"},
    )
    assert response.status_code == 403


@pytest.mark.anyio
async def test_login_rate_limit_returns_429(client, monkeypatch):
    class RejectAll:
        def check(self, key):
            return False

    monkeypatch.setattr(main_module, "login_limiter", RejectAll())
    response = await client.post(
        "/login",
        data={"password": "wrong"},
        headers={"origin": "http://test"},
    )
    assert response.status_code == 429
    assert response.json()["detail"] == "登录尝试过于频繁，请稍后重试"


@pytest.mark.anyio
async def test_render_forwarded_https_origin_is_accepted(monkeypatch):
    monkeypatch.setattr(
        auth_module,
        "settings",
        SimpleNamespace(
            app_password="local-dev-password",
            trust_render_proxy=True,
        ),
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://pdf-tool.onrender.com",
        follow_redirects=False,
    ) as proxy_client:
        response = await proxy_client.post(
            "/login",
            data={"password": "local-dev-password"},
            headers={
                "origin": "https://pdf-tool.onrender.com",
                "x-forwarded-proto": "https",
            },
        )
    assert response.status_code == 303
