from fastapi import FastAPI, Depends, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from app import models
from app.database import engine, get_db
import os
from pathlib import Path  # مكتبة التعامل مع المسارات بذكاء

# --- 1. تحديد المسار الرئيسي للمشروع بدقة (Absolute Path) ---
# هذا السطر هو الحل السحري لمشاكل "File Not Found"
BASE_DIR = Path(__file__).resolve().parent

# --- استيراد الروابط ---
from app.api import search, export, auth, suggestions, admin, payments, chat

# إنشاء جداول قاعدة البيانات
models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="24Seven Sales Intelligence Platform",
    description="Professional SaaS Platform.",
    version="2.1.0"
)

# --- 2. إعدادات CORS ---
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
# نستخدم BASE_DIR لضمان العثور على مجلد static أينما كان السيرفر
static_path = BASE_DIR / "static"
upload_path = static_path / "uploads"

# التأكد من وجود مجلد التحميلات
os.makedirs(upload_path, exist_ok=True)

# ربط المسار (Mount)
# نستخدم str(static_path) لتحويل المسار الذكي إلى نص يفهمه FastAPI
app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

# --- 5. المسارات (Routes) ---
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(search.router, prefix="/search", tags=["Search Engine"])
app.include_router(export.router, prefix="/export", tags=["Data Export"])
app.include_router(suggestions.router, prefix="/ai", tags=["AI Engine"])
app.include_router(admin.router, prefix="/admin", tags=["Admin Dashboard"])
app.include_router(payments.router, prefix="/payments", tags=["Payments"])
app.include_router(chat.router, prefix="/chat", tags=["Customer Support Chat"])

# --- 6. الواجهة الرئيسية (مع كاشف الأخطاء) ---
@app.get("/")
async def read_root():
    # نستخدم المسار الكامل للملف
    file_path = BASE_DIR / "dashboard.html"
    
    # المحاولة الأولى: هل الملف موجود؟ افتحه فوراً
    if file_path.exists():
        return FileResponse(file_path)
    
    # المحاولة الثانية (Debug): إذا لم يجد الملف، اعرض لي ماذا يوجد في المجلد!
    # هذا سيساعدنا لنعرف هل الاسم مكتوب بحرف كبير أو بامتداد مختلف
    try:
        files_in_dir = [f.name for f in BASE_DIR.iterdir() if f.is_file()]
        files_list_html = "</li><li>".join(files_in_dir)
        
        error_message = f"""
        <html>
            <body style="font-family: sans-serif; text-align: center; padding: 50px;">
                <h1 style="color: red;">Error: dashboard.html not found!</h1>
                <p><strong>Server is looking in:</strong><br> {BASE_DIR}</p>
                <hr>
                <h3>Files actually found in this directory:</h3>
                <ul style="text-align: left; display: inline-block;">
                    <li>{files_list_html}</li>
                </ul>
                <p><em>Please check if 'dashboard.html' is in the list above exactly as written.</em></p>
            </body>
        </html>
        """
        return HTMLResponse(error_message)
    except Exception as e:
        return HTMLResponse(f"<h1>Critical Error</h1><p>{str(e)}</p>")

@app.get("/admin-panel")
async def read_admin_panel():
    file_path = BASE_DIR / "admin.html"
    
    if file_path.exists():
        return FileResponse(file_path)
        
    return HTMLResponse(f"<h1>Error: admin.html not found!</h1><p>Looking in: {file_path}</p>")

# --- 7. Setup ---
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