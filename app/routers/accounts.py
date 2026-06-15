import asyncio
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field, validator

from .. import sub2api_client as api
from ..deps import templates
from ..security import require_session

router = APIRouter(prefix="/accounts")
ACCOUNT_META_TTL_SECONDS = 10 * 60
WINDOW_SECONDS = {"5h": 5 * 3600, "7d": 7 * 24 * 3600}
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
    # 使用被动采样数据，避免访问详情页时触发上游订阅/限速接口的主动查询。
    usage_t = api.get_account_usage(account_id, source="passive")
    stats_t = api.get_account_stats(account_id, days=30)
    today_t = api.get_account_today_stats(account_id)
    now = datetime.now(timezone.utc)
    trend_t = api.get_usage_trend_for_account(
        account_id,
        (now - timedelta(days=8)).astimezone().strftime("%Y-%m-%d"),
        now.astimezone().strftime("%Y-%m-%d"),
        granularity="hour",
    )

    results = await asyncio.gather(account_t, usage_t, stats_t, today_t, trend_t, return_exceptions=True)
    account, usage, stats, today, trend = results
    def safe(v): return None if isinstance(v, Exception) else v
    errors = [str(v) for v in results if isinstance(v, Exception)]

    return templates.TemplateResponse(
        "account_detail.html",
        {
            "request": request,
            "active": "accounts",
            "account": safe(account) or {"id": account_id},
            "usage": safe(usage),
            "windows": _build_windows(safe(usage), safe(trend), now),
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


def _num(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _num_or_none(value) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _first_value(*values):
    for value in values:
        if value is not None:
            return value
    return None


def _get_any(item: dict, *keys: str):
    for key in keys:
        value = item.get(key)
        if value is not None:
            return value
    return None


def _normalize_series(data: Any) -> list[dict]:
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if not isinstance(data, dict):
        return []
    for key in ("history", "data", "items", "stats", "trend"):
        value = data.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def _parse_dt(value) -> Optional[datetime]:
    if not value:
        return None
    raw = str(value).strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        dt = None
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d %H", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(raw, fmt)
                break
            except ValueError:
                continue
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _parse_trend_dt(value) -> Optional[datetime]:
    """解析 trend/history 的时间点，返回本地时区 naive datetime，与接口整点 label 对齐。"""
    if not value:
        return None
    raw = str(value).strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        dt = None
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d %H", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(raw, fmt)
                break
            except ValueError:
                continue
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt.astimezone().replace(tzinfo=None)
    return dt


def _sum_trend(trend: Any, since: datetime, until: datetime) -> Optional[dict]:
    series = _normalize_series(trend)
    if not series:
        return None

    since_local = since.astimezone().replace(tzinfo=None)
    until_local = until.astimezone().replace(tzinfo=None)
    agg = {"requests": 0, "tokens": 0, "actual_cost": 0.0, "user_cost": None}
    matched = False
    for point in series:
        dt = _parse_trend_dt(_get_any(point, "date", "time", "bucket", "label", "Date", "Time", "Bucket", "Label"))
        if dt is None or dt < since_local or dt >= until_local:
            continue
        matched = True
        agg["requests"] += int(_num(_get_any(point, "requests", "total_requests", "Requests", "TotalRequests")))
        agg["tokens"] += int(_num(_get_any(point, "total_tokens", "tokens", "TotalTokens", "Tokens")))
        agg["actual_cost"] += _num(_get_any(
            point,
            "standard_cost",
            "total_standard_cost",
            "actual_cost",
            "total_actual_cost",
            "cost",
            "total_cost",
            "StandardCost",
            "TotalStandardCost",
            "ActualCost",
            "TotalActualCost",
            "Cost",
            "TotalCost",
        ))
        user_cost = _get_any(point, "user_cost", "total_user_cost", "UserCost", "TotalUserCost")
        if user_cost is not None:
            if agg["user_cost"] is None:
                agg["user_cost"] = 0.0
            agg["user_cost"] += _num(user_cost)
    return agg if matched else None


def _has_stats(stats: dict) -> bool:
    return any(stats.get(key) is not None for key in ("requests", "tokens", "actual_cost", "user_cost"))


def _window_bounds(label: str, src: dict, now: datetime) -> tuple[datetime, datetime]:
    reset_at = _parse_dt(src.get("resets_at"))
    remaining_seconds = _num_or_none(src.get("remaining_seconds"))
    if reset_at is None or reset_at <= now:
        reset_at = now + timedelta(seconds=remaining_seconds) if remaining_seconds and remaining_seconds > 0 else now

    window_start = reset_at - timedelta(seconds=WINDOW_SECONDS[label])
    return window_start, min(reset_at, now)


def _estimate_quota(used, pct) -> Optional[float]:
    """上游不返回额度时，用本地窗口用量和利用率反推预计总额度。"""
    used_num = _num_or_none(used)
    pct_num = _num_or_none(pct)
    if used_num is None or pct_num is None or used_num <= 0 or pct_num <= 0:
        return None
    return used_num * 100 / pct_num


def _build_windows(usage: Optional[dict], trend: Any = None, now: Optional[datetime] = None) -> list[dict]:
    """把 account usage 的 five_hour / seven_day 转成统一的窗口列表。"""
    if not isinstance(usage, dict):
        return []
    now = now or datetime.now(timezone.utc)
    mapping = [("5h", "five_hour"), ("7d", "seven_day")]
    out: list[dict] = []
    for label, src_key in mapping:
        src = usage.get(src_key)
        if not isinstance(src, dict):
            continue
        raw_window_stats = src.get("window_stats")
        has_window_stats = isinstance(raw_window_stats, dict)
        ws = raw_window_stats if has_window_stats else {}
        window_stats = {
            "requests": ws.get("requests"),
            "tokens": ws.get("tokens"),
            "actual_cost": _first_value(ws.get("standard_cost"), ws.get("actual_cost"), ws.get("cost")),
            "user_cost": ws.get("user_cost"),
        }
        if label == "7d":
            window_start, window_end = _window_bounds(label, src, now)
            window_stats = _sum_trend(trend, window_start, window_end) or {
                "requests": None,
                "tokens": None,
                "actual_cost": None,
                "user_cost": None,
            }

        pct = src.get("utilization")
        estimated_quota = _estimate_quota(_first_value(window_stats.get("actual_cost"), window_stats.get("user_cost")), pct)
        out.append({
            "label": label,
            "has_window_stats": has_window_stats,
            "has_stats": _has_stats(window_stats),
            "requests": window_stats.get("requests"),
            "tokens": window_stats.get("tokens"),
            "actual_cost": window_stats.get("actual_cost"),
            "user_cost": window_stats.get("user_cost"),
            "pct": pct,
            "estimated_quota": estimated_quota,
            "remaining_seconds": src.get("remaining_seconds"),
            "resets_at": src.get("resets_at"),
        })
    return out
