"""上游 /api/v1/admin/dashboard/trend 接口的共享消费工具。

字段契约（2026-06 实测确认）：
- 顶层响应: {"start_date", "end_date", "granularity", "trend": [point, ...]}
- 数据点 point: date, requests, input_tokens, output_tokens,
  cache_creation_tokens, cache_read_tokens, total_tokens, cost, actual_cost
- date 格式: "YYYY-MM-DD HH:MM"，本地时间（与请求的本地日期范围对齐）

被 accounts / api_keys 两个详情页共用，消除重复实现并统一时区/成本口径。
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

# 成本字段口径：优先 actual_cost（实际成本语义），回退 standard_cost / cost。
# 不把 cost 当 actual_cost 混用——trend 的 cost 在详情页作为 user_cost 展示，与 actual_cost 区分。
_COST_KEYS = ("actual_cost", "standard_cost", "cost")
_DT_FORMATS = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d %H", "%Y-%m-%d")


def to_float(value: Any) -> float:
    """转 float，失败返回 0.0。"""
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def to_float_or_none(value: Any) -> Optional[float]:
    """转 float，失败返回 None（用于需区分"0"与"缺失"的场景）。"""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _try_parse(raw: str) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        for fmt in _DT_FORMATS:
            try:
                return datetime.strptime(raw, fmt)
            except ValueError:
                continue
    return None


def parse_dt(value: Any) -> Optional[datetime]:
    """解析带时区语义的时间（如 resets_at），返回 UTC-aware datetime；naive 按 UTC 处理。"""
    if not value:
        return None
    dt = _try_parse(str(value).strip().replace("Z", "+00:00"))
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _parse_local_naive(value: Any) -> Optional[datetime]:
    """解析 trend 的 date label，返回本地时区的 naive datetime，与窗口边界对齐。"""
    if not value:
        return None
    dt = _try_parse(str(value).strip().replace("Z", "+00:00"))
    if dt is None:
        return None
    return dt.astimezone().replace(tzinfo=None) if dt.tzinfo is not None else dt


def extract_series(resp: Any) -> list[dict]:
    """从 trend 响应取出数据点列表（契约 resp['trend']）；兼容直接传入列表。"""
    if isinstance(resp, list):
        return [p for p in resp if isinstance(p, dict)]
    if isinstance(resp, dict) and isinstance(resp.get("trend"), list):
        return [p for p in resp["trend"] if isinstance(p, dict)]
    return []


def pick_cost(stats: Optional[dict]) -> Optional[float]:
    """按口径优先级提取成本（actual_cost 优先）；逐字段尝试，跳过无法解析的坏值。"""
    if not isinstance(stats, dict):
        return None
    for key in _COST_KEYS:
        value = to_float_or_none(stats.get(key))
        if value is not None:
            return value
    return None


def sum_trend(
    series: list[dict],
    since: datetime,
    until: Optional[datetime] = None,
) -> Optional[dict]:
    """对 [since, until) 时间窗内的数据点求和（until 省略则无上界）。

    时间统一在本地 naive 维度比较：since/until 转本地 naive，trend date 本就是本地 label。
    无法解析时间的点被跳过（不计入求和）。
    返回 None 表示窗口内无匹配数据点（区别于命中但全为 0）。
    """
    points = [p for p in series if isinstance(p, dict)]
    if not points:
        return None

    since_local = since.astimezone().replace(tzinfo=None)
    until_local = until.astimezone().replace(tzinfo=None) if until else None

    agg = {"requests": 0, "tokens": 0, "cost": 0.0, "actual_cost": 0.0}
    matched = False
    for point in points:
        dt = _parse_local_naive(point.get("date"))
        if dt is None or dt < since_local:
            continue
        if until_local is not None and dt >= until_local:
            continue
        matched = True
        agg["requests"] += int(to_float(point.get("requests")))
        agg["tokens"] += int(to_float(point.get("total_tokens")))
        agg["cost"] += to_float(point.get("cost"))
        agg["actual_cost"] += to_float(point.get("actual_cost"))
    return agg if matched else None
