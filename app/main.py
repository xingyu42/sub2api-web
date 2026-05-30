from contextlib import asynccontextmanager
import re

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware
from starlette_csrf import CSRFMiddleware

from .config import settings
from .deps import templates
from .limiter import limiter
from .routers import accounts, api_keys, auth, dashboard
from .sub2api_client import Sub2APIError, close_client, get_client


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """添加安全响应头中间件"""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # 防止 MIME 类型嗅探
        response.headers["X-Content-Type-Options"] = "nosniff"

        # 防止点击劫持
        response.headers["X-Frame-Options"] = "DENY"

        # Referrer 策略
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # 权限策略
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"

        # 内容安全策略
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' https://cdn.jsdelivr.net; "
            "style-src 'self'; "
            "img-src 'self' data:; "
            "font-src 'self'; "
            "connect-src 'self' https://cdn.jsdelivr.net; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self'"
        )

        return response


def sanitize_error_message(exc: Exception) -> str:
    """清理错误信息中的敏感数据"""
    msg = str(exc)[:500]  # 先限制长度，防止 ReDoS

    # 移除 IP 地址
    msg = re.sub(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}', '[IP]', msg)

    # 移除端口号
    msg = re.sub(r':\d{2,5}', ':[PORT]', msg)

    # 移除文件路径（Windows 和 Unix）
    msg = re.sub(r'[A-Za-z]:[\\\/][^\s]+', '[PATH]', msg)
    msg = re.sub(r'/[^\s]+', '[PATH]', msg)

    # 限制最终长度
    return msg[:200]


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_client()  # 立即初始化，便于 DNS/TLS 失败时尽早暴露
    yield
    await close_client()


app = FastAPI(title="sub2api 用量", lifespan=lifespan)

# 配置速率限制器
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# 添加 CSRF 保护中间件
app.add_middleware(
    CSRFMiddleware,
    secret=settings.SESSION_SECRET,
    exempt_urls=[re.compile(r"^/login$"), re.compile(r"^/logout$")],
    cookie_name="csrf_token",
    header_name="X-CSRF-Token",
    cookie_secure=settings.COOKIE_SECURE,
    cookie_samesite="lax",
)

# 添加安全响应头中间件（必须在其他中间件之前）
app.add_middleware(SecurityHeadersMiddleware)

app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(accounts.router)
app.include_router(api_keys.router)


@app.exception_handler(Sub2APIError)
async def sub2api_error_handler(request: Request, exc: Sub2APIError):
    return templates.TemplateResponse(
        "error.html",
        {"request": request, "active": None,
            "status": exc.status, "message": exc.message},
        status_code=502 if exc.status >= 500 else exc.status,
    )


@app.exception_handler(httpx.RequestError)
async def httpx_error_handler(request: Request, exc: httpx.RequestError):
    if settings.DEBUG:
        safe_message = sanitize_error_message(exc)
        message = f"网络连接错误：{safe_message}"
    else:
        message = "网络连接错误，请稍后重试"

    return templates.TemplateResponse(
        "error.html",
        {
            "request": request,
            "active": None,
            "status": 0,
            "message": message,
        },
        status_code=502,
    )


@app.get("/healthz", response_class=HTMLResponse)
async def healthz():
    return "ok"
