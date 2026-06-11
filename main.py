from fastapi import FastAPI, Depends, Request, Query
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from app import models
from app.database import engine, get_db
import os
from pathlib import Path
from dotenv import load_dotenv

# تحميل متغيرات البيئة من ملف .env
load_dotenv()

# --- 1. تحديد المسار الرئيسي للمشروع بدقة (Absolute Path) ---
BASE_DIR = Path(__file__).resolve().parent

# --- استيراد الروابط (APIs) ---
# تأكد من وجود مجلد app/api وبداخله هذه الملفات
from app.api import search, export, auth, suggestions, admin, payments, chat, ai, daily_report
from app.api.scheduler import start_scheduler, stop_scheduler

# إنشاء جداول قاعدة البيانات
models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="24Seven Sales Intelligence Platform",
    description="Professional SaaS Platform.",
    version="2.6.0"
)

@app.on_event("startup")
async def startup_event():
    start_scheduler()

@app.on_event("shutdown")
async def shutdown_event():
    stop_scheduler()

# --- 2. إعدادات CORS (السماح بالاتصال من أي مكان) ---
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

# ========================================================
# --- 4. إعداد الملفات الثابتة (Static & Images) ---
# ========================================================

# أ) إعداد مجلد static (للملفات العامة CSS/JS)
static_path = BASE_DIR / "static"
upload_path = static_path / "uploads"
os.makedirs(upload_path, exist_ok=True) 
app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

# ب) إعداد مجلد images (لصور السيارات واللوجوهات) ✅
images_path = BASE_DIR / "images"
os.makedirs(images_path, exist_ok=True) 
app.mount("/images", StaticFiles(directory=str(images_path)), name="images")


# --- 5. المسارات الخلفية (Backend Routes) ---
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(search.router, prefix="/search", tags=["Search Engine"])
app.include_router(export.router, prefix="/export", tags=["Data Export"])
app.include_router(suggestions.router, prefix="/ai", tags=["AI Engine"])
app.include_router(admin.router, prefix="/admin", tags=["Admin Dashboard"])
app.include_router(payments.router, prefix="/payments", tags=["Payments"])
app.include_router(chat.router, prefix="/chat", tags=["Customer Support Chat"])
app.include_router(ai.router, prefix="/api", tags=["AI Dashboard Helpers"])
app.include_router(daily_report.router, prefix="/api/reports", tags=["Daily Reports"])

# ==========================================
# 🌐 Omnichannel Direct Endpoints (No Auth Needed)
# Used by moderator.html on production (Render)
# ==========================================
import requests as _req

_WA_TOKEN = "EAAPDbwUyvY0BQrm6ZB9qb62LU9hI50ZC9QOfZAO3VPA7ZCSnFSRMCb2kouBRkXu4LiVmRU2ydv1vLl00kKmgTFMN5ULJOpImor7i8oITjicjIjWiOLxTL7yltYrlF0RLxcdU6UNOaIdqo4Ouv0BnQ79OK2sgSLpHY9ZCQs4iRIxcpjnoxr8EWpV4FSgGTzgZDZD"
_PHONE_ID = "597129733493778"
_FB_TOKEN = "EAAPDbwUyvY0BRN0VW4bIHPLRpeA7qHqK5TyFpNxJ8fuFcvVCshuBwZC52F59Q6oNH671nLZBbAiEsGSB55Vq0sHjyMIB4QNStzt6sFxRL7ImzttrnuFkHVTYWGZC0J2MgbBGfqo3dOi7Wo5QagQ7pY3vhZAztfKZBhNZCxGrVeGRIqz7pUkHHC2iM4ZA0mDje9oEXZCm"
_IG_TOKEN = "IGAAMRP14aPG1BZAGJmSTBHdjY1UGp5VEFjLTYzdGZAKaHRLaWE1Y2FuczNaeUhRYnAyRjdWX25vbktxb0xkZAEIyaWRwU2RKd201bFNaT0RzQk5INXhSTnczYnJSYUJWY05IVTBHSlQzX0libWlfTDNmZAXhROG40bmg0c2dWM2N2QQZDZD"  # Updated 2026-06-12
_SB_URL = "https://wtjwzqvmwnbvjxnmweqq.supabase.co"
_SB_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Ind0and6cXZtd25idmp4bm13ZXFxIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzE0NjU0MDMsImV4cCI6MjA4NzA0MTQwM30.kTFK22b18cc1BmvMyLTt-7V113jyf_YrodSB7Km00tY"
_SB_HEADERS = {"apikey": _SB_KEY, "Authorization": f"Bearer {_SB_KEY}", "Content-Type": "application/json"}

# --- Messenger Webhook State ---
_FB_VERIFY_TOKEN = "messenger_secret_24seven"
processed_mids = set()
sent_via_api_mids = set()

def get_facebook_user_name(sender_id):
    """
    استدعاء Graph API لجلب اسم المستخدم من ماسنجر بناءً على الـ PSID
    """
    # محاولة 1: عبر محادثات الصفحة
    try:
        url = "https://graph.facebook.com/v18.0/me/conversations"
        params = {
            "access_token": _FB_TOKEN,
            "user_id": sender_id,
            "fields": "participants"
        }
        r = _req.get(url, params=params, timeout=5)
        if r.status_code == 200:
            data = r.json()
            for conv in data.get('data', []):
                for p in conv.get('participants', {}).get('data', []):
                    if str(p.get('id')) == str(sender_id):
                        name = p.get('name', '').strip()
                        if name:
                            print(f"[FB->Render] Found Name via conversations: {name} (ID: {sender_id})")
                            return name
        else:
            print(f"[FB->Render] Conversations lookup failed: {r.status_code} | {r.text}")
    except Exception as e:
        print(f"[ERROR->Render] Exception in conversations lookup for {sender_id}: {e}")

    # محاولة 2: عبر Graph API المباشر للملف الشخصي (fallback)
    parameters = {
        "fields": "first_name,last_name",
        "access_token": _FB_TOKEN
    }
    url = f"https://graph.facebook.com/v18.0/{sender_id}"
    try:
        r = _req.get(url, params=parameters, timeout=5)
        if r.status_code == 200:
            data = r.json()
            first = data.get('first_name', '')
            last = data.get('last_name', '')
            name = f"{first} {last}".strip()
            if name:
                print(f"[FB->Render] Found FB Name: {name} (ID: {sender_id})")
                return name
        else:
            print(f"[FB->Render] Direct profile lookup failed: {r.status_code} | {r.text}")
    except Exception as e:
        print(f"[ERROR->Render] Exception in get_facebook_user_name direct lookup: {e}")
    
    return "Messenger User"

@app.get("/api/health")
async def health_check():
    return {"status": "ok", "server": "24seven-render"}

@app.post("/api/send_reply")
async def send_reply_direct(data: dict):
    """نقطة إرسال موحدة للموديتور - واتساب وماسنجر وإنستجرام - تعمل مباشرة من Render بدون ngrok"""
    channel = (data.get("channel") or "").lower()
    sender_id = data.get("sender_id", "")
    message = data.get("message", "")
    mod_name = data.get("mod_name", "Admin")

    if not channel or not sender_id or not message:
        return {"status": "error", "detail": "Missing parameters"}

    # --- إرسال الرسالة ---
    if channel == "whatsapp":
        url = f"https://graph.facebook.com/v17.0/{_PHONE_ID}/messages"
        headers = {"Authorization": f"Bearer {_WA_TOKEN}", "Content-Type": "application/json"}
        payload = {"messaging_product": "whatsapp", "to": sender_id, "type": "text", "text": {"body": message}}
        try:
            r = _req.post(url, headers=headers, json=payload, timeout=10)
            if r.status_code not in [200, 201]:
                print(f"❌ WA Send failed: {r.text}")
        except Exception as e:
            print(f"❌ WA exception: {e}")

    elif channel == "messenger":
        url = f"https://graph.facebook.com/v18.0/me/messages?access_token={_FB_TOKEN}"
        payload = {"recipient": {"id": sender_id}, "message": {"text": message}}
        try:
            r = _req.post(url, headers={"Content-Type": "application/json"}, json=payload, timeout=10)
            if r.status_code == 200:
                try:
                    fb_msg_id = r.json().get('message_id', '')
                    if fb_msg_id:
                        sent_via_api_mids.add(fb_msg_id)
                        if len(sent_via_api_mids) > 500: sent_via_api_mids.clear()
                        print(f"[FB-API->Render] Tracked MID: {fb_msg_id}")
                except: pass
            else:
                print(f"❌ Messenger Send failed: {r.text}")
        except Exception as e:
            print(f"❌ Messenger exception: {e}")

    elif channel == "instagram":
        url = f"https://graph.facebook.com/v17.0/me/messages?access_token={_FB_TOKEN}"
        payload = {"recipient": {"id": sender_id}, "message": {"text": message}}
        try:
            r = _req.post(url, headers={"Content-Type": "application/json"}, json=payload, timeout=10)
            if r.status_code == 200:
                try:
                    ig_msg_id = r.json().get('message_id', '')
                    if ig_msg_id:
                        sent_via_api_mids.add(ig_msg_id)
                        if len(sent_via_api_mids) > 500: sent_via_api_mids.clear()
                        print(f"[IG-API->Render] Tracked MID: {ig_msg_id}")
                except: pass
            else:
                print(f"❌ Instagram Send failed: {r.text}")
        except Exception as e:
            print(f"❌ Instagram exception: {e}")

    # --- حفظ الرسالة في Supabase ---
    sb_payload = {
        "channel": channel,
        "sender_id": sender_id,
        "sender_name": mod_name,
        "message_text": message,
        "is_from_admin": True,
        "read_by_admin": True
    }
    try:
        _req.post(f"{_SB_URL}/rest/v1/omnichannel_messages", headers=_SB_HEADERS, json=sb_payload, timeout=5)
    except Exception as e:
        print(f"❌ Supabase save exception: {e}")

    return {"status": "success"}

# ==========================================
# 📥 Messenger Webhook - رسائل ماسنجر الواردة
# ==========================================
@app.get("/messenger")
async def verify_messenger_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
    hub_verify_token: str = Query(None, alias="hub.verify_token")
):
    """تحقق من webhook Meta لماسنجر"""
    from fastapi.responses import PlainTextResponse
    if hub_verify_token == _FB_VERIFY_TOKEN and hub_mode == "subscribe":
        return PlainTextResponse(hub_challenge or "")
    return PlainTextResponse("Forbidden", status_code=403)

@app.post("/messenger")
async def receive_messenger_webhook(request: Request):
    """استقبل رسائل ماسنجر الواردة وحفظها في Supabase"""
    try:
        data = await request.json()
        if data.get("object") != "page" or not data.get("entry"):
            return {"status": "ok"}

        for entry in data["entry"]:
            events = entry.get("messaging", []) or entry.get("standby", [])
            for event in events:
                if "delivery" in event or "read" in event:
                    continue

                sender_id = event["sender"]["id"]
                text = None
                message = event.get("message", {}) or event.get("message_edit", {})
                mid = message.get("mid")

                # منع التكرار
                if mid:
                    if mid in processed_mids:
                        print(f"[FB->Render] Skipping duplicate Messenger MID: {mid}")
                        continue
                    processed_mids.add(mid)
                    if len(processed_mids) > 10000:
                        processed_mids.clear()

                if "message" in event or "message_edit" in event:
                    if message.get("is_echo"):
                        admin_text = message.get("text", "").strip()
                        target_user_id = event["recipient"]["id"]
                        echo_mid = message.get("mid", "")

                        if echo_mid in sent_via_api_mids:
                            print(f"[FB->Render] (Echo) Admin via API to {target_user_id}: {admin_text} [SKIP - saved by send_reply]")
                            sent_via_api_mids.discard(echo_mid)
                        else:
                            print(f"[FB->Render] (Echo) Admin via Page to {target_user_id}: {admin_text} [SAVING - direct from FB]")
                            _req.post(
                                f"{_SB_URL}/rest/v1/omnichannel_messages",
                                headers=_SB_HEADERS,
                                json={
                                    "channel": "messenger",
                                    "sender_id": target_user_id,
                                    "sender_name": "Admin",
                                    "message_text": admin_text,
                                    "is_from_admin": True,
                                    "read_by_admin": True
                                },
                                timeout=5
                            )
                        continue

                    if "quick_reply" in message:
                        text = message["quick_reply"].get("payload")
                    elif "text" in message:
                        text = message["text"]

                elif "postback" in event:
                    text = event["postback"].get("payload")
                    mid = f"pb_{sender_id}_{event.get('timestamp')}_{text}"
                    if mid in processed_mids:
                        continue
                    processed_mids.add(mid)

                if not text:
                    continue

                print(f"[FB->Render] from {sender_id}: {text}")

                # تحديد اسم المرسل
                sender_name = get_facebook_user_name(sender_id)

                # حفظ في Supabase
                _req.post(
                    f"{_SB_URL}/rest/v1/omnichannel_messages",
                    headers=_SB_HEADERS,
                    json={
                        "channel": "messenger",
                        "sender_id": sender_id,
                        "sender_name": sender_name,
                        "message_text": text,
                        "is_from_admin": False,
                        "read_by_admin": False
                    },
                    timeout=5
                )
    except Exception as e:
        print(f"[Messenger-Webhook Error]: {e}")

    return {"status": "ok"}

# ==========================================
# 📥 Instagram Webhook - رسائل إنستجرام الواردة
# ==========================================
_IG_VERIFY_TOKEN = "24seven_secret_token"

@app.get("/api/instagram/webhook")
async def verify_instagram_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
    hub_verify_token: str = Query(None, alias="hub.verify_token")
):
    """تحقق من webhook Meta لإنستجرام"""
    from fastapi.responses import PlainTextResponse
    if hub_verify_token == _IG_VERIFY_TOKEN and hub_mode == "subscribe":
        return PlainTextResponse(hub_challenge or "")
    return PlainTextResponse("Forbidden", status_code=403)

@app.post("/api/instagram/webhook")
async def receive_instagram_webhook(request: Request):
    """استقبل رسائل إنستجرام الواردة وحفظها في Supabase بعد جلب اسم المستخدم"""
    try:
        data = await request.json()
        if data.get("object") != "instagram" or not data.get("entry"):
            return {"status": "ok"}

        for entry in data["entry"]:
            messaging_events = entry.get("messaging", []) or entry.get("standby", [])
            for event in messaging_events:
                sender_id = event.get("sender", {}).get("id")
                recipient_id = event.get("recipient", {}).get("id")
                message = event.get("message", {}) or event.get("message_edit", {})

                if not sender_id or not message or "text" not in message:
                    continue

                mid = message.get("mid")
                # منع التكرار
                if mid:
                    if mid in processed_mids:
                        print(f"[IG->Render] Skipping duplicate Instagram MID: {mid}")
                        continue
                    processed_mids.add(mid)
                    if len(processed_mids) > 10000:
                        processed_mids.clear()

                text_body = message.get("text", "")

                # معالجة الـ Echoes (الردود من الأدمن)
                if message.get("is_echo"):
                    target_user_id = recipient_id
                    if mid in sent_via_api_mids:
                        print(f"[IG->Render] (Echo) Admin via API to {target_user_id}: {text_body} [SKIP - saved by send_reply]")
                        sent_via_api_mids.discard(mid)
                    else:
                        print(f"[IG->Render] (Echo) Admin via Business Suite to {target_user_id}: {text_body} [SAVING]")
                        _req.post(
                            f"{_SB_URL}/rest/v1/omnichannel_messages",
                            headers=_SB_HEADERS,
                            json={
                                "channel": "instagram",
                                "sender_id": target_user_id,
                                "sender_name": "Admin",
                                "message_text": text_body,
                                "is_from_admin": True,
                                "read_by_admin": True
                            },
                            timeout=5
                        )
                    continue

                print(f"[IG->Render] from {sender_id}: {text_body}")

                # جلب اسم الحساب من Meta API
                sender_name = "Instagram User"
                try:
                    profile_res = _req.get(
                        f"https://graph.facebook.com/v17.0/{sender_id}",
                        params={"fields": "username", "access_token": _FB_TOKEN},
                        timeout=5
                    )
                    if profile_res.status_code == 200:
                        profile_data = profile_res.json()
                        if profile_data.get("username"):
                            sender_name = profile_data["username"]
                except Exception as ex:
                    print(f"[IG Profile Error] Failed to fetch IG profile for {sender_id}: {ex}")

                # حفظ في Supabase
                _req.post(
                    f"{_SB_URL}/rest/v1/omnichannel_messages",
                    headers=_SB_HEADERS,
                    json={
                        "channel": "instagram",
                        "sender_id": sender_id,
                        "sender_name": sender_name,
                        "message_text": text_body,
                        "is_from_admin": False,
                        "read_by_admin": False
                    },
                    timeout=5
                )
    except Exception as e:
        print(f"[IG-Webhook Error]: {e}")

    return {"status": "ok"}

# ==========================================
# 📥 WhatsApp Webhook - رسائل واتساب الواردة
# يستقبل الرسائل مباشرة من Meta على الـ production server
# ==========================================
_WA_VERIFY_TOKEN = "24seven_secret_token"

@app.get("/webhook")
async def verify_whatsapp_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
    hub_verify_token: str = Query(None, alias="hub.verify_token")
):
    """تحقق من webhook Meta لواتساب"""
    from fastapi.responses import PlainTextResponse
    if hub_verify_token == _WA_VERIFY_TOKEN and hub_mode == "subscribe":
        return PlainTextResponse(hub_challenge or "")
    return PlainTextResponse("Forbidden", status_code=403)

@app.post("/webhook")
async def receive_whatsapp_webhook(request: Request):
    """استقبال رسائل واتساب الواردة وحفظها في Supabase"""
    try:
        data = await request.json()
        if not data.get("entry"):
            return {"status": "ok"}

        changes = data["entry"][0].get("changes", [{}])[0].get("value", {})
        messages = changes.get("messages", [])

        for msg in messages:
            sender = msg.get("from", "")
            msg_type = msg.get("type", "text")
            text_body = ""

            if msg_type == "text":
                text_body = msg.get("text", {}).get("body", "")
            elif msg_type == "interactive":
                inter = msg.get("interactive", {})
                text_body = inter.get("button_reply", inter.get("list_reply", {})).get("title", "")
            elif msg_type == "button":
                text_body = msg.get("button", {}).get("text", "")
            elif msg_type == "location":
                loc = msg.get("location", {})
                text_body = f"📍 لوكيشن: {loc.get('latitude')}, {loc.get('longitude')}"

            if not text_body:
                continue

            print(f"[WA->Render] from {sender}: {text_body}")

            # تحديد اسم المرسل
            sender_name = sender
            try:
                clean = sender.replace("+", "").replace("0020", "20")
                local = clean[2:] if clean.startswith("20") else clean
                r_name = _req.get(
                    f"{_SB_URL}/rest/v1/google_reservations",
                    headers=_SB_HEADERS,
                    params={"customer_phone": f"ilike.%{local}%", "select": "customer_name", "limit": "1"},
                    timeout=5
                )
                if r_name.status_code == 200:
                    rows = r_name.json()
                    if rows and rows[0].get("customer_name"):
                        sender_name = rows[0]["customer_name"]
            except Exception:
                pass

            # حفظ في Supabase
            _req.post(
                f"{_SB_URL}/rest/v1/omnichannel_messages",
                headers=_SB_HEADERS,
                json={
                    "channel": "whatsapp",
                    "sender_id": sender,
                    "sender_name": sender_name,
                    "message_text": text_body,
                    "is_from_admin": False,
                    "read_by_admin": False
                },
                timeout=5
            )
    except Exception as e:
        print(f"[WA-Webhook Error]: {e}")

    return {"status": "ok"}

# ==========================================
#  نظام التوجيه والواجهات (Frontend Routing)
# ==========================================

# 1. الصفحة الرئيسية (Landing Page) ✅
@app.get("/")
async def read_root():
    # الأولوية لصفحة الهوم الجديدة
    file_path = BASE_DIR / "home.html"
    if file_path.exists():
        return FileResponse(file_path)
    
    # حل احتياطي
    fallback = BASE_DIR / "index.html"
    if fallback.exists():
        return FileResponse(fallback)
        
    return HTMLResponse("<h1>Error: home.html not found! Please check GitHub files.</h1>")

# مسار مباشر لصفحة home.html
@app.get("/home.html")
async def read_home_page():
    file_path = BASE_DIR / "home.html"
    if file_path.exists():
        return FileResponse(file_path)
    return HTMLResponse("<h1>Error: home.html not found!</h1>", status_code=404)

# 2. صفحة من نحن (الجديدة - تمت الإضافة) ✅
@app.get("/about.html")
async def read_about_page():
    file_path = BASE_DIR / "about.html"
    if file_path.exists():
        return FileResponse(file_path)
    return HTMLResponse("<h1>Error: about.html not found!</h1>", status_code=404)

# 3. صفحة الاستثمار ✅
@app.get("/invest.html")
async def read_invest_page():
    file_path = BASE_DIR / "invest.html"
    if file_path.exists():
        return FileResponse(file_path)
    return HTMLResponse("<h1>Error: invest.html not found!</h1>", status_code=404)

# 4. صفحة آراء العملاء ✅
@app.get("/reviews.html")
async def read_reviews_page():
    file_path = BASE_DIR / "reviews.html"
    if file_path.exists():
        return FileResponse(file_path)
    return HTMLResponse("<h1>Error: reviews.html not found!</h1>", status_code=404)

# 5. صفحة حجز الليموزين (للعملاء) ✅
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

# 6. لوحة تحكم الأدمن (ERP System) ✅
@app.get("/admin-panel")
async def read_admin_panel():
    file_path = BASE_DIR / "admin-crm.html"
    if file_path.exists():
        return FileResponse(file_path)
    return HTMLResponse("<h1>Error: admin-crm.html not found! Please make sure you uploaded the file.</h1>", status_code=404)

# 7. صفحة المشاريع (إضافية)
@app.get("/projects.html")
async def read_projects_page():
    file_path = BASE_DIR / "projects.html"
    if file_path.exists():
        return FileResponse(file_path)
    return HTMLResponse("<h1>Error: projects.html not found!</h1>")

# 8. صفحة العروض (Web Design)
@app.get("/web-design")
async def read_web_design_page():
    file_path = BASE_DIR / "web_design.html"
    if file_path.exists():
        return FileResponse(file_path)
    return HTMLResponse("<h1>Error: web_design.html not found!</h1>")

# 9. صفحة الأداة القديمة (اختياري)
@app.get("/dashboard")
async def read_app_dashboard():
    file_path = BASE_DIR / "dashboard.html"
    if file_path.exists():
        return FileResponse(file_path)
    return HTMLResponse("<h1>Error: dashboard.html not found!</h1>", status_code=404)


# --- Setup Admin (خاص بقاعدة البيانات المحلية SQL - للتطوير فقط) ---
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