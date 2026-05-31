import asyncio
import re
import time
from typing import Optional

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field, validator

from .. import sub2api_client as api
from ..deps import templates
from ..security import require_session

router = APIRouter(prefix="/accounts")
ACCOUNT_META_TTL_SECONDS = 10 * 60
_account_meta_cache: dict[int, tuple[float, dict]] = {}


class AccountFilters(BaseModel):
    """账号列表查询参数验证"""
    platform: str = Field("", max_length=50, pattern=r'^[a-zA-Z0-9_-]*$')
    status: str = Field("", max_length=20, pattern=r'^[a-zA-Z0-9_-]*$')
    search: str = Field("", max_length=100)

    @validator('search')
    def sanitize_search(cls, v):
        # 移除潜在危险字符
        return re.sub(r'[<>"\']', '', v)


@router.get("", response_class=HTMLResponse)
async def list_view(
    request: Request,
    filters: AccountFilters = Depends(),
):
    redirect = require_session(request)
    if redirect:
        return redirect

    page_data = await api.list_accounts(
        page=1,
        page_size=200,
        lite=True,
        platform=filters.platform or None,
        status=filters.status or None,
        search=filters.search or None,
    )
    items = page_data.get("items") or []
    _warm_account_meta_cache(items)

    ids = [int(a["id"]) for a in items if a.get("id") is not None]
    today_stats_raw: dict = {}
    if ids:
        try:
            today_stats_raw = await api.batch_today_stats(ids) or {}
        except api.Sub2APIError:
            today_stats_raw = {}

    today_map = today_stats_raw.get("stats") if isinstance(
        today_stats_raw, dict) else None
    if today_map is None and isinstance(today_stats_raw, dict):
        today_map = today_stats_raw
    today_map = today_map or {}

    for a in items:
        key = str(a.get("id"))
        a["_today"] = today_map.get(key) or today_map.get(int(key)) or {}

    return templates.TemplateResponse(
        "accounts.html",
        {
            "request": request,
            "active": "accounts",
            "items": items,
            "total": page_data.get("total", len(items)),
            "filters": {"platform": filters.platform, "status": filters.status, "search": filters.search},
        },
    )


@router.get("/{account_id}", response_class=HTMLResponse)
async def detail_view(request: Request, account_id: int):
    redirect = require_session(request)
    if redirect:
        return redirect

    account_t = _get_account_meta(account_id)
    usage_t = api.get_account_usage(account_id)
    stats_t = api.get_account_stats(account_id, days=30)
    today_t = api.get_account_today_stats(account_id)

    results = await asyncio.gather(account_t, usage_t, stats_t, today_t, return_exceptions=True)
    account, usage, stats, today = results
    def safe(v): return None if isinstance(v, Exception) else v
    errors = [str(v) for v in results if isinstance(v, Exception)]

    return templates.TemplateResponse(
        "account_detail.html",
        {
            "request": request,
            "active": "accounts",
            "account": safe(account) or {"id": account_id},
            "usage": safe(usage),
            "windows": _build_windows(safe(usage)),
            "stats": safe(stats),
            "today": safe(today),
            "errors": errors,
        },
    )


def _warm_account_meta_cache(accounts: list[dict]) -> None:
    for account in accounts:
        _set_account_meta_cache(account)


def _set_account_meta_cache(account: dict) -> None:
    account_id = account.get("id")
    if account_id is None:
        return
    try:
        key = int(account_id)
    except (TypeError, ValueError):
        return

    meta = {k: v for k, v in account.items() if not str(k).startswith("_")}
    _account_meta_cache[key] = (time.monotonic(), meta)


def _get_account_meta_cache(account_id: int) -> Optional[dict]:
    cached = _account_meta_cache.get(int(account_id))
    if cached is None:
        return None

    cached_at, account = cached
    if time.monotonic() - cached_at > ACCOUNT_META_TTL_SECONDS:
        _account_meta_cache.pop(int(account_id), None)
        return None
    return dict(account)


async def _get_account_meta(account_id: int) -> dict:
    cached = _get_account_meta_cache(account_id)
    if cached is not None:
        return cached

    account = await api.get_account(account_id)
    if isinstance(account, dict):
        _set_account_meta_cache(account)
    return account


def _build_windows(usage: Optional[dict]) -> list[dict]:
    """把 account usage 的 five_hour / seven_day 转成统一的窗口列表。"""
    if not isinstance(usage, dict):
        return []
    mapping = [("5h", "five_hour"), ("7d", "seven_day")]
    out: list[dict] = []
    for label, src_key in mapping:
        src = usage.get(src_key)
        if not isinstance(src, dict):
            continue
        raw_window_stats = src.get("window_stats")
        has_window_stats = isinstance(raw_window_stats, dict)
        ws = raw_window_stats if has_window_stats else {}
        out.append({
            "label": label,
            "has_window_stats": has_window_stats,
            "requests": ws.get("requests"),
            "tokens": ws.get("tokens"),
            "actual_cost": ws.get("standard_cost"),
            "user_cost": ws.get("user_cost"),
            "pct": src.get("utilization"),
            "remaining_seconds": src.get("remaining_seconds"),
            "resets_at": src.get("resets_at"),
        })
    return out
