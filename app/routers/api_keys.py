from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from .. import sub2api_client as api
from ..deps import templates
from ..security import require_session

router = APIRouter(prefix="/api-keys")

# 各窗口长度（秒）
WINDOWS = {
    "5h": 5 * 3600,
    "1d": 24 * 3600,
    "7d": 7 * 24 * 3600,
}


def _num(v) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


@router.get("", response_class=HTMLResponse)
async def list_view(request: Request):
    redirect = require_session(request)
    if redirect:
        return redirect

    keys = await api.collect_all_api_keys()
    ids = [int(k["id"]) for k in keys if k.get("id") is not None]
    usage_raw: dict = {}
    if ids:
        try:
            usage_raw = await api.batch_api_keys_usage(ids) or {}
        except api.Sub2APIError:
            usage_raw = {}
    stats_map = usage_raw.get("stats") if isinstance(usage_raw, dict) else {}
    stats_map = stats_map or {}
    now = datetime.now(timezone.utc)
    updated_at = now.astimezone().strftime("%Y-%m-%d %H:%M:%S")
    for k in keys:
        sid = str(k.get("id"))
        k["_usage"] = stats_map.get(sid) or {}
        k["_windows"] = []
        for w in ("5h", "1d", "7d"):
            seconds = WINDOWS[w]
            limit = _num(k.get(f"rate_limit_{w}"))
            used = _num(k.get(f"usage_{w}"))
            pct = round(used / limit * 100, 1) if limit > 0 else None
            win_start = _parse_dt(k.get(f"window_{w}_start"))
            if win_start is not None:
                reset_at = win_start + timedelta(seconds=seconds)
                remaining = _humanize((reset_at - now).total_seconds())
            else:
                remaining = None
            k["_windows"].append({
                "label": w,
                "pct": pct,
                "limit": limit,
                "used": used,
                "remaining": remaining,
            })
    items = sorted(
        keys,
        key=lambda k: _num(k.get("_usage", {}).get("total_actual_cost")),
        reverse=True,
    )
    total = len(items)

    return templates.TemplateResponse(
        "api_keys.html",
        {
            "request": request,
            "active": "api-keys",
            "items": items,
            "total": total,
            "updated_at": updated_at,
        },
    )


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        s = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def _humanize(seconds: float) -> str:
    if seconds <= 0:
        return "已重置"
    seconds = int(seconds)
    d, rem = divmod(seconds, 86400)
    h, rem = divmod(rem, 3600)
    m, _ = divmod(rem, 60)
    if d > 0:
        return f"{d}d {h}h"
    if h > 0:
        return f"{h}h {m}m"
    return f"{m}m"


def _sum_trend(trend: list[dict], since: datetime) -> dict:
    """汇总 trend 中 since 之后的点。trend 的 date 字段格式为 'YYYY-MM-DD HH:MM' 或 'YYYY-MM-DD'（视为本地时间）。"""
    agg = {"requests": 0, "tokens": 0, "actual_cost": 0.0, "cost": 0.0}
    since_naive = since.astimezone().replace(tzinfo=None)
    for p in trend or []:
        raw = p.get("date") or ""
        dt = None
        for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(raw, fmt)
                break
            except ValueError:
                continue
        if dt is not None and dt < since_naive:
            continue
        agg["requests"] += int(_num(p.get("requests")))
        agg["tokens"] += int(_num(p.get("total_tokens")))
        agg["actual_cost"] += _num(p.get("actual_cost"))
        agg["cost"] += _num(p.get("cost"))
    return agg


@router.get("/{key_id}", response_class=HTMLResponse)
async def detail_view(request: Request, key_id: int):
    redirect = require_session(request)
    if redirect:
        return redirect

    key = await api.find_api_key(key_id)
    if key is None:
        return templates.TemplateResponse(
            "error.html",
            {"request": request, "active": "api-keys", "status": 404,
             "message": f"未找到 API Key #{key_id}"},
            status_code=404,
        )

    now = datetime.now(timezone.utc)
    # 拉最近 8 天的小时级 trend（覆盖 7d 窗口），按 api_key_id 过滤
    start_date = (now - timedelta(days=8)).astimezone().strftime("%Y-%m-%d")
    end_date = now.astimezone().strftime("%Y-%m-%d")
    trend_resp = await api.get_usage_trend_for_key(key_id, start_date, end_date, granularity="hour")
    trend = trend_resp.get("trend") if isinstance(trend_resp, dict) else []

    windows = []
    for w, seconds in WINDOWS.items():
        since = now - timedelta(seconds=seconds)
        agg = _sum_trend(trend, since)
        limit = _num(key.get(f"rate_limit_{w}"))
        used = _num(key.get(f"usage_{w}"))
        win_start = _parse_dt(key.get(f"window_{w}_start"))
        pct = round(used / limit * 100, 1) if limit > 0 else None
        if win_start is not None:
            reset_at = win_start + timedelta(seconds=seconds)
            remaining = _humanize((reset_at - now).total_seconds())
        else:
            remaining = "—"
        windows.append({
            "label": w,
            "requests": agg["requests"],
            "tokens": agg["tokens"],
            "actual_cost": agg["actual_cost"],
            "user_cost": agg["cost"],
            "limit": limit,
            "used": used,
            "pct": pct,
            "remaining": remaining,
        })

    return templates.TemplateResponse(
        "api_key_detail.html",
        {
            "request": request,
            "active": "api-keys",
            "key": key,
            "windows": windows,
            "updated_at": now.astimezone().strftime("%Y-%m-%d %H:%M:%S"),
        },
    )
