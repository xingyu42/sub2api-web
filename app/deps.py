from pathlib import Path

from fastapi.templating import Jinja2Templates
from jinja2 import Undefined


TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def fmt_int(value) -> str:
    if value is None or isinstance(value, Undefined):
        return "0"
    try:
        return f"{int(float(value)):,}"
    except (TypeError, ValueError):
        return "0"


def fmt_money(value, decimals: int = 4) -> str:
    if value is None or isinstance(value, Undefined):
        return "$0.0000"
    try:
        return f"${float(value):,.{decimals}f}"
    except (TypeError, ValueError):
        return "$0.0000"


def fmt_dt(value) -> str:
    if not value or isinstance(value, Undefined):
        return "-"
    return str(value)[:19].replace("T", " ")


def fmt_compact(value) -> str:
    if value is None or isinstance(value, Undefined):
        return "0"
    try:
        n = float(value)
    except (TypeError, ValueError):
        return "0"
    for threshold, suffix in ((1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K")):
        if abs(n) >= threshold:
            return f"{n / threshold:.1f}{suffix}"
    return str(int(n))


def fmt_duration(value) -> str:
    if value is None or isinstance(value, Undefined):
        return "—"
    try:
        seconds = int(float(value))
    except (TypeError, ValueError):
        return "—"
    if seconds <= 0:
        return "已重置"
    d, rem = divmod(seconds, 86400)
    h, rem = divmod(rem, 3600)
    m, _ = divmod(rem, 60)
    if d > 0:
        return f"{d}d {h}h"
    if h > 0:
        return f"{h}h {m}m"
    return f"{m}m"


templates.env.filters["fmt_int"] = fmt_int
templates.env.filters["fmt_money"] = fmt_money
templates.env.filters["fmt_dt"] = fmt_dt
templates.env.filters["fmt_compact"] = fmt_compact
templates.env.filters["fmt_duration"] = fmt_duration


# 暴露 CSP nonce 到模板（延迟导入避免循环依赖）
def _get_csp_nonce_wrapper():
    from .main import get_csp_nonce
    return get_csp_nonce()


templates.env.globals['csp_nonce'] = _get_csp_nonce_wrapper
