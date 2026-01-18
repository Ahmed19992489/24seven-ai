from fastapi import FastAPI, Depends, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from app import models
from app.database import engine, get_db
import os
from pathlib import Path

# --- 1. تحديد المسار الرئيسي للمشروع بدقة (Absolute Path) ---
# هذا السطر يضمن أن السيرفر يرى الملفات أينما كان مكانه
BASE_DIR = Path(__file__).resolve().parent

# --- استيراد الروابط (APIs) ---
from app.api import search, export, auth, suggestions, admin, payments, chat

# إنشاء جداول قاعدة البيانات
models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="24Seven Sales Intelligence Platform",
    description="Professional SaaS Platform.",
    version="2.2.0"
)

# --- 2. إعدادات CORS (السماح بالاتصال) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 3. إضافة هيدرز الأمان ---
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin-allow-popups"
    return response

# --- 4. إعداد الملفات الثابتة (Static Files) ---
# هذا السطر مهم جداً لكي تظهر الصور وملفات الـ CSS
static_path = BASE_DIR / "static"
upload_path = static_path / "uploads"

# التأكد من وجود مجلد التحميلات
os.makedirs(upload_path, exist_ok=True)

# ربط المسار (Mount)
app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

# --- 5. المسارات الخلفية (Backend Routes) ---
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(search.router, prefix="/search", tags=["Search Engine"])
app.include_router(export.router, prefix="/export", tags=["Data Export"])
app.include_router(suggestions.router, prefix="/ai", tags=["AI Engine"])
app.include_router(admin.router, prefix="/admin", tags=["Admin Dashboard"])
app.include_router(payments.router, prefix="/payments", tags=["Payments"])
app.include_router(chat.router, prefix="/chat", tags=["Customer Support Chat"])

# ==========================================
#  نظام التوجيه والواجهات (Frontend Routing)
# ==========================================

# 1. الصفحة الرئيسية (تفتح موقع الشركة التعريفي)
@app.get("/")
async def read_company_site():
    file_path = BASE_DIR / "index.html"
    if file_path.exists():
        return FileResponse(file_path)
    return HTMLResponse("<h1>Error: index.html not found! Please upload the website file.</h1>")

# 2. صفحة المشاريع (Portfolio)
@app.get("/projects.html")
async def read_projects_page():
    file_path = BASE_DIR / "projects.html"
    if file_path.exists():
        return FileResponse(file_path)
    return HTMLResponse("<h1>Error: projects.html not found!</h1>")

# 3. (جديد) صفحة عروض تصميم المواقع (Web Design Offers)
@app.get("/web-design")
async def read_web_design_page():
    file_path = BASE_DIR / "web_design.html"
    if file_path.exists():
        return FileResponse(file_path)
    return HTMLResponse("<h1>Error: web_design.html not found!</h1>")

# 4. صفحة الأداة (Dashboard) - يدخل لها العميل من زر تسجيل الدخول
@app.get("/dashboard")
async def read_app_dashboard():
    file_path = BASE_DIR / "dashboard.html"
    if file_path.exists():
        return FileResponse(file_path)
    return HTMLResponse("<h1>Error: dashboard.html not found!</h1>")

# 5. لوحة تحكم الأدمن
@app.get("/admin-panel")
async def read_admin_panel():
    file_path = BASE_DIR / "admin.html"
    if file_path.exists():
        return FileResponse(file_path)
    return HTMLResponse("<h1>Error: admin.html not found!</h1>")

# --- Setup Admin (لإنشاء حساب الأدمن الأول مرة واحدة) ---
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