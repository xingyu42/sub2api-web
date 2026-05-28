from __future__ import annotations

import asyncio
from typing import Any, Optional

import httpx

from .config import settings


class Sub2APIError(Exception):
    def __init__(self, status: int, message: str, code: Optional[int] = None):
        self.status = status
        self.message = message
        self.code = code
        super().__init__(f"[{status}] {message}")


_client: Optional[httpx.AsyncClient] = None


def get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        # 如果提供了 CA 证书路径则使用，否则使用系统默认（强制验证）
        # 不再允许通过配置禁用 SSL 验证，提升安全性
        verify = settings.SUB2API_CA_BUNDLE if settings.SUB2API_CA_BUNDLE else True
        
        _client = httpx.AsyncClient(
            base_url=settings.SUB2API_BASE_URL.rstrip("/"),
            headers={
                "x-api-key": settings.SUB2API_ADMIN_KEY,
                "Accept": "application/json",
            },
            timeout=settings.REQUEST_TIMEOUT,
            verify=verify,  # 强制验证，不可禁用
        )
    return _client


async def close_client() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


def _unwrap(resp: httpx.Response) -> Any:
    if resp.status_code >= 500:
        raise Sub2APIError(resp.status_code, _safe_message(resp) or "sub2api 服务异常")
    try:
        body = resp.json()
    except ValueError as exc:
        raise Sub2APIError(resp.status_code, f"非 JSON 响应：{resp.text[:200]}") from exc

    if resp.status_code >= 400 or (isinstance(body, dict) and body.get("code") not in (0, None)):
        message = body.get("message") or body.get("reason") or resp.reason_phrase or "请求失败"
        code = body.get("code") if isinstance(body, dict) else None
        raise Sub2APIError(resp.status_code, message, code=code)

    if isinstance(body, dict) and "data" in body:
        return body["data"]
    return body


def _safe_message(resp: httpx.Response) -> str:
    try:
        body = resp.json()
        if isinstance(body, dict):
            return body.get("message") or body.get("reason") or ""
    except ValueError:
        pass
    return resp.text[:200] if resp.text else ""


async def _get(path: str, **params: Any) -> Any:
    cleaned = {k: v for k, v in params.items() if v is not None and v != ""}
    resp = await get_client().get(path, params=cleaned)
    return _unwrap(resp)


async def _post(path: str, json: Optional[dict] = None) -> Any:
    resp = await get_client().post(path, json=json or {})
    return _unwrap(resp)


# ---------- Dashboard ----------

async def get_dashboard_stats() -> dict:
    return await _get("/api/v1/admin/dashboard/stats")


async def get_usage_trend(start_date: str, end_date: str, granularity: str = "day") -> dict:
    return await _get(
        "/api/v1/admin/dashboard/trend",
        start_date=start_date,
        end_date=end_date,
        granularity=granularity,
    )


async def get_usage_trend_for_key(
    api_key_id: int, start_date: str, end_date: str, granularity: str = "hour"
) -> dict:
    return await _get(
        "/api/v1/admin/dashboard/trend",
        api_key_id=api_key_id,
        start_date=start_date,
        end_date=end_date,
        granularity=granularity,
    )


async def get_model_stats(start_date: str, end_date: str) -> Any:
    return await _get(
        "/api/v1/admin/dashboard/models",
        start_date=start_date,
        end_date=end_date,
    )


# ---------- Accounts (上游账号) ----------

async def list_accounts(
    page: int = 1,
    page_size: int = 100,
    lite: bool = True,
    platform: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
) -> dict:
    return await _get(
        "/api/v1/admin/accounts",
        page=page,
        page_size=page_size,
        lite="true" if lite else "false",
        platform=platform,
        status=status,
        search=search,
    )


async def get_account(account_id: int) -> dict:
    return await _get(f"/api/v1/admin/accounts/{account_id}")


async def get_account_usage(account_id: int, source: str = "active") -> dict:
    return await _get(f"/api/v1/admin/accounts/{account_id}/usage", source=source)


async def get_account_stats(account_id: int, days: int = 30) -> Any:
    return await _get(f"/api/v1/admin/accounts/{account_id}/stats", days=days)


async def get_account_today_stats(account_id: int) -> dict:
    return await _get(f"/api/v1/admin/accounts/{account_id}/today-stats")


async def batch_today_stats(account_ids: list[int]) -> Any:
    if not account_ids:
        return {}
    return await _post("/api/v1/admin/accounts/today-stats/batch", json={"account_ids": account_ids})


# ---------- Users & API Keys ----------

async def list_users(page: int = 1, page_size: int = 100) -> dict:
    return await _get("/api/v1/admin/users", page=page, page_size=page_size)


async def list_user_api_keys(user_id: int) -> Any:
    return await _get(f"/api/v1/admin/users/{user_id}/api-keys")


async def batch_api_keys_usage(api_key_ids: list[int]) -> Any:
    if not api_key_ids:
        return {"stats": {}}
    return await _post(
        "/api/v1/admin/dashboard/api-keys-usage",
        json={"api_key_ids": api_key_ids},
    )


async def collect_all_users() -> list[dict]:
    """分页拉完所有用户。"""
    page = 1
    page_size = 100
    out: list[dict] = []
    while True:
        data = await list_users(page=page, page_size=page_size)
        items = data.get("items") or data.get("users") or []
        out.extend(items)
        total = data.get("total")
        if total is None:
            if len(items) < page_size:
                break
        else:
            if len(out) >= total or not items:
                break
        page += 1
        if page > 200:  # 安全栏
            break
    return out


async def collect_all_api_keys(concurrency: int = 8) -> list[dict]:
    """枚举所有用户 → 拉每个用户的 API Key，组装成扁平列表。"""
    users = await collect_all_users()
    sem = asyncio.Semaphore(concurrency)

    async def fetch(u: dict) -> list[dict]:
        async with sem:
            try:
                raw = await list_user_api_keys(u["id"])
            except Sub2APIError:
                return []
        keys = raw if isinstance(raw, list) else raw.get("items") or raw.get("api_keys") or []
        for k in keys:
            k["_user_id"] = u.get("id")
            k["_user_email"] = u.get("email") or u.get("username") or u.get("nickname")
        return keys

    chunks = await asyncio.gather(*(fetch(u) for u in users))
    flat: list[dict] = []
    for c in chunks:
        flat.extend(c)
    return flat


async def find_api_key(key_id: int) -> Optional[dict]:
    """枚举所有用户的 Key，找到指定 ID（admin 路由没有直接的 GET /admin/api-keys/:id）。"""
    keys = await collect_all_api_keys()
    for k in keys:
        if int(k.get("id", -1)) == int(key_id):
            return k
    return None
