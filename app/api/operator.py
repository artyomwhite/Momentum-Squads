from fastapi import APIRouter,Request,Form
from fastapi.responses import HTMLResponse,RedirectResponse
from sqlalchemy import select
from app.db import SessionLocal
from app.models import Ticket
from app.config import get_settings
from fastapi.templating import Jinja2Templates
templates=Jinja2Templates(directory="app/templates")
router=APIRouter()
@router.get("/",response_class=HTMLResponse)
async def dashboard(request:Request):
    if not request.session.get("operator"):return RedirectResponse("/login",303)
    async with SessionLocal() as s:rows=(await s.scalars(select(Ticket).order_by(Ticket.created_at.desc()))).all()
    return templates.TemplateResponse(request=request,name="dashboard.html",context={"tickets":rows})
@router.get("/login",response_class=HTMLResponse)
async def login_page(request:Request):
    return templates.TemplateResponse(request=request,name="login.html",context={"error":None})
@router.post("/login")
async def login(request:Request,username:str=Form(...),password:str=Form(...)):
    cfg=get_settings()
    if username!=cfg.operator_username or password!=cfg.operator_password:
        return templates.TemplateResponse(request=request,name="login.html",context={"error":"Invalid credentials"},status_code=401)
    request.session["operator"]=username
    return RedirectResponse("/",303)
@router.post("/logout")
async def logout(request:Request):
    request.session.clear();return RedirectResponse("/login",303)
