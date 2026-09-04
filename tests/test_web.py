import httpx
import pytest

from app.main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_home_page_contains_converter_controls():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        await client.post(
            "/login",
            data={"password": "local-dev-password"},
            headers={"origin": "http://test"},
        )
        response = await client.get("/")

    assert response.status_code == 200
    assert "PDF 转 Word" in response.text
    assert 'id="drop-zone"' in response.text
    assert 'id="convert-button"' in response.text
    assert 'id="progress-bar"' in response.text
    assert "30 MB" in response.text
    assert "100 页" in response.text
    assert "首次打开可能需要约一分钟" in response.text
    assert 'action="/logout"' in response.text


@pytest.mark.anyio
async def test_static_assets_are_served_locally():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        css = await client.get("/static/styles.css")
        javascript = await client.get("/static/app.js")

    assert css.status_code == 200
    assert "--forest: #1a3c2b" in css.text.lower()
    assert javascript.status_code == 200
    assert "/api/convert" in javascript.text
    assert 'response.status === 401' in javascript.text
    assert 'response.status === 404' in javascript.text
