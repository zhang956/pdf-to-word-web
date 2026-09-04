import hmac
from urllib.parse import urlsplit

from fastapi import HTTPException, Request

from app.config import settings


def is_authenticated(request: Request) -> bool:
    return request.session.get("authenticated") is True


def require_api_auth(request: Request) -> None:
    if not is_authenticated(request):
        raise HTTPException(status_code=401, detail="请先登录")


def password_matches(candidate: str) -> bool:
    return hmac.compare_digest(candidate.encode(), settings.app_password.encode())


def validate_same_origin(request: Request) -> None:
    supplied = request.headers.get("origin") or request.headers.get("referer")
    if not supplied:
        raise HTTPException(status_code=403, detail="请求来源无效")
    source = urlsplit(supplied)
    expected = urlsplit(str(request.base_url))
    expected_scheme = expected.scheme
    if settings.trust_render_proxy:
        forwarded_proto = request.headers.get("x-forwarded-proto", "")
        if forwarded_proto:
            expected_scheme = forwarded_proto.split(",")[-1].strip()
    expected_host = request.headers.get("host", expected.netloc)
    if (source.scheme, source.netloc) != (expected_scheme, expected_host):
        raise HTTPException(status_code=403, detail="请求来源无效")
