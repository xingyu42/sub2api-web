from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from ..deps import templates
from ..security import clear_session, is_authenticated, issue_session, verify_password

router = APIRouter()


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    if is_authenticated(request):
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@router.post("/login", response_class=HTMLResponse)
async def login_submit(request: Request, password: str = Form(...)):
    if not verify_password(password):
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "密码错误"},
            status_code=401,
        )
    resp = RedirectResponse("/", status_code=303)
    issue_session(resp)
    return resp


@router.post("/logout")
async def logout():
    resp = RedirectResponse("/login", status_code=303)
    clear_session(resp)
    return resp
