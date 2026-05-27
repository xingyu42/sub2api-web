import asyncio
from typing import Optional

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse

from .. import sub2api_client as api
from ..deps import templates
from ..security import require_session

router = APIRouter(prefix="/accounts")


@router.get("", response_class=HTMLResponse)
async def list_view(
    request: Request,
    platform: str = Query(""),
    status: str = Query(""),
    search: str = Query(""),
):
    redirect = require_session(request)
    if redirect:
        return redirect

    page_data = await api.list_accounts(
        page=1,
        page_size=200,
        lite=True,
        platform=platform or None,
        status=status or None,
        search=search or None,
    )
    items = page_data.get("items") or []

    ids = [int(a["id"]) for a in items if a.get("id") is not None]
    today_stats_raw: dict = {}
    if ids:
        try:
            today_stats_raw = await api.batch_today_stats(ids) or {}
        except api.Sub2APIError:
            today_stats_raw = {}

    today_map = today_stats_raw.get("stats") if isinstance(today_stats_raw, dict) else None
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
            "filters": {"platform": platform, "status": status, "search": search},
        },
    )


@router.get("/{account_id}", response_class=HTMLResponse)
async def detail_view(request: Request, account_id: int):
    redirect = require_session(request)
    if redirect:
        return redirect

    account_t = api.get_account(account_id)
    usage_t = api.get_account_usage(account_id)
    stats_t = api.get_account_stats(account_id, days=30)
    today_t = api.get_account_today_stats(account_id)

    results = await asyncio.gather(account_t, usage_t, stats_t, today_t, return_exceptions=True)
    account, usage, stats, today = results
    safe = lambda v: None if isinstance(v, Exception) else v
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
        ws = src.get("window_stats") or {}
        out.append({
            "label": label,
            "requests": ws.get("requests"),
            "tokens": ws.get("tokens"),
            "actual_cost": ws.get("standard_cost"),  # 截图里的 "A"
            "user_cost": ws.get("user_cost"),         # 截图里的 "U"
            "pct": src.get("utilization"),
            "remaining_seconds": src.get("remaining_seconds"),
            "resets_at": src.get("resets_at"),
        })
    return out
