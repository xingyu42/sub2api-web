from datetime import date, timedelta

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from .. import sub2api_client as api
from ..deps import templates
from ..security import require_session

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    redirect = require_session(request)
    if redirect:
        return redirect

    today = date.today()
    start = today - timedelta(days=6)
    end = today

    stats = await api.get_dashboard_stats()
    trend = await api.get_usage_trend(start.isoformat(), end.isoformat(), granularity="day")
    models = await api.get_model_stats(start.isoformat(), end.isoformat())

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "active": "dashboard",
            "stats": stats,
            "trend": trend,
            "models": models,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
        },
    )
