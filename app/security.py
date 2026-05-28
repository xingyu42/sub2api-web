import hmac
from typing import Optional

from fastapi import Request
from fastapi.responses import RedirectResponse, Response
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from .config import settings

SESSION_COOKIE_NAME = "sub2api_web_session"
SESSION_MAX_AGE = 7 * 24 * 3600
SESSION_PAYLOAD = "ok"

_serializer = URLSafeTimedSerializer(settings.SESSION_SECRET, salt="sub2api-web")


def verify_password(plain: str) -> bool:
    return hmac.compare_digest(plain.encode("utf-8"), settings.LOGIN_PASSWORD.encode("utf-8"))


def issue_session(response: Response) -> None:
    token = _serializer.dumps(SESSION_PAYLOAD)
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=settings.COOKIE_SECURE,  # 从配置读取，生产环境强制启用
    )


def clear_session(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE_NAME)


def is_authenticated(request: Request) -> bool:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        return False
    try:
        _serializer.loads(token, max_age=SESSION_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return False
    return True


def require_session(request: Request) -> Optional[RedirectResponse]:
    if is_authenticated(request):
        return None
    return RedirectResponse(url="/login", status_code=303)
