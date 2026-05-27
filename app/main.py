from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from .deps import templates
from .routers import accounts, api_keys, auth, dashboard
from .sub2api_client import Sub2APIError, close_client, get_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_client()  # 立即初始化，便于 DNS/TLS 失败时尽早暴露
    yield
    await close_client()


app = FastAPI(title="sub2api 用量", lifespan=lifespan)

app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(accounts.router)
app.include_router(api_keys.router)


@app.exception_handler(Sub2APIError)
async def sub2api_error_handler(request: Request, exc: Sub2APIError):
    return templates.TemplateResponse(
        "error.html",
        {"request": request, "active": None, "status": exc.status, "message": exc.message},
        status_code=502 if exc.status >= 500 else exc.status,
    )


@app.exception_handler(httpx.RequestError)
async def httpx_error_handler(request: Request, exc: httpx.RequestError):
    return templates.TemplateResponse(
        "error.html",
        {
            "request": request,
            "active": None,
            "status": 0,
            "message": f"网络/连接错误：{exc!s}",
        },
        status_code=502,
    )


@app.get("/healthz", response_class=HTMLResponse)
async def healthz():
    return "ok"
