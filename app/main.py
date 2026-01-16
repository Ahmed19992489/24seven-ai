from fastapi import FastAPI, Depends, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from app import models
from app.database import engine, get_db
import os

# --- استيراد الروابط ---
from app.api import search, export, auth, suggestions, admin, payments, chat

models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="24Seven Sales Intelligence Platform",
    description="Professional SaaS Platform.",
    version="2.1.0"
)

# 1. إعدادات CORS (للموبايل و Ngrok واللاب توب)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. إضافة هيدرز الأمان الضرورية لجوجل ولحماية المتصفح
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    # حل مشكلة الشاشة البيضاء مع جوجل
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin-allow-popups"
    return response

# --- 📁 إعداد الملفات الثابتة (الحل الجذري لخطأ الصور) ---
# التأكد من وجود المجلدات
os.makedirs("static/uploads", exist_ok=True)

# ربط المسار /static ليقرأ محتويات مجلد static الفعلي
app.mount("/static", StaticFiles(directory="static"), name="static")

# --- المسارات (Routes) ---
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(search.router, prefix="/search", tags=["Search Engine"])
app.include_router(export.router, prefix="/export", tags=["Data Export"])
app.include_router(suggestions.router, prefix="/ai", tags=["AI Engine"])
app.include_router(admin.router, prefix="/admin", tags=["Admin Dashboard"])
app.include_router(payments.router, prefix="/payments", tags=["Payments"])
app.include_router(chat.router, prefix="/chat", tags=["Customer Support Chat"])

# --- الواجهة الرئيسية ---
@app.get("/")
async def read_root():
    if os.path.exists("dashboard.html"):
        return FileResponse("dashboard.html")
    return HTMLResponse("<h1>Error: dashboard.html not found!</h1>")

@app.get("/admin-panel")
async def read_admin_panel():
    if os.path.exists("admin.html"):
        return FileResponse("admin.html")
    return HTMLResponse("<h1>Error: admin.html not found!</h1>")

# --- Setup ---
@app.post("/setup-admin/", tags=["Admin & Setup"])
def create_founder_account(db: Session = Depends(get_db)):
    existing_user = db.query(models.User).filter(models.User.email == "admin@24seven.com").first()
    if existing_user:
        return {"message": "Exists"}
    
    from app.utils.auth_utils import get_password_hash
    new_user = models.User(
        email="admin@24seven.com", 
        full_name="Ahmed Hashem",
        hashed_password=get_password_hash("admin123"),
        company_name="24Seven Limousine", 
        credits=10000
    )
    db.add(new_user)
    db.commit()
    return {"message": "Created", "user": new_user.email}