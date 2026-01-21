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
BASE_DIR = Path(__file__).resolve().parent

# --- استيراد الروابط (APIs) ---
# تأكد من وجود مجلد app/api وبداخله هذه الملفات
from app.api import search, export, auth, suggestions, admin, payments, chat

# إنشاء جداول قاعدة البيانات
models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="24Seven Sales Intelligence Platform",
    description="Professional SaaS Platform.",
    version="2.4.0"
)

# --- 2. إعدادات CORS (السماح بالاتصال من أي مكان) ---
# هذا ضروري جداً لكي يعمل الفرونت إند مع الباك إند على الدومين
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
    # هذا الهيدر مهم أحياناً لعمليات المصادقة (Auth)
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin-allow-popups"
    return response

# ========================================================
# --- 4. إعداد الملفات الثابتة (Static & Images) ---
# ========================================================

# أ) إعداد مجلد static (للملفات العامة CSS/JS)
static_path = BASE_DIR / "static"
upload_path = static_path / "uploads"
os.makedirs(upload_path, exist_ok=True) # ينشئ المجلد لو مش موجود
app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

# ب) إعداد مجلد images (لصور السيارات في صفحة الليموزين) ✅
images_path = BASE_DIR / "images"
os.makedirs(images_path, exist_ok=True) # ينشئ المجلد لو مش موجود
app.mount("/images", StaticFiles(directory=str(images_path)), name="images")


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

# 1. الصفحة الرئيسية
@app.get("/")
async def read_company_site():
    file_path = BASE_DIR / "index.html"
    if file_path.exists():
        return FileResponse(file_path)
    return HTMLResponse("<h1>Error: index.html not found! Please check GitHub files.</h1>")

# 2. صفحة المشاريع
@app.get("/projects.html")
async def read_projects_page():
    file_path = BASE_DIR / "projects.html"
    if file_path.exists():
        return FileResponse(file_path)
    return HTMLResponse("<h1>Error: projects.html not found!</h1>")

# 3. صفحة العروض (Web Design)
@app.get("/web-design")
async def read_web_design_page():
    file_path = BASE_DIR / "web_design.html"
    if file_path.exists():
        return FileResponse(file_path)
    return HTMLResponse("<h1>Error: web_design.html not found!</h1>")

# 4. صفحة الأداة (Dashboard - القديمة)
@app.get("/dashboard")
async def read_app_dashboard():
    file_path = BASE_DIR / "dashboard.html"
    if file_path.exists():
        return FileResponse(file_path)
    return HTMLResponse("<h1>Error: dashboard.html not found!</h1>", status_code=404)

# 5. لوحة تحكم الأدمن (تم التعديل للملف الجديد admin-crm.html) ✅
@app.get("/admin-panel")
async def read_admin_panel():
    # هنا تم توجيه الرابط لفتح ملف الداش بورد الجديد المتكامل
    file_path = BASE_DIR / "admin-crm.html"
    if file_path.exists():
        return FileResponse(file_path)
    return HTMLResponse("<h1>Error: admin-crm.html not found! Please make sure you uploaded the file.</h1>", status_code=404)

# 6. صفحة حجز الليموزين (للعملاء)
@app.get("/limousine.html")
async def read_limousine_page():
    file_path = BASE_DIR / "limousine.html"
    if file_path.exists():
        return FileResponse(file_path)
    return HTMLResponse("<h1>Error: limousine.html not found! Please check file name.</h1>", status_code=404)

# مسار إضافي لفتح صفحة الليموزين بدون .html
@app.get("/limousine")
async def read_limousine_clean():
    return await read_limousine_page()

# --- Setup Admin (خاص بقاعدة البيانات المحلية SQL) ---
# ملاحظة: Supabase يستخدم نظام Auth منفصل، هذا الكود للـ Local Testing
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

if __name__ == "__main__":
    import uvicorn
    # إعدادات التشغيل لـ Render
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)