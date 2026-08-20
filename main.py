from fastapi import FastAPI, Depends, Request, Query
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
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

gateway_process = None

@app.on_event("startup")
async def startup_event():
    start_scheduler()
    
    # تشغيل بوابة الواتساب المحلية بلغة Node.js في الخلفية
    global gateway_process
    import subprocess
    try:
        gateway_dir = os.path.join(os.path.dirname(__file__), "whatsapp_gateway")
        if os.path.exists(gateway_dir):
            if not os.path.exists(os.path.join(gateway_dir, "node_modules")):
                print("[Gateway] Installing Node.js dependencies...")
                subprocess.run("npm install", shell=True, cwd=gateway_dir, check=True)
            
            print("[Gateway] Starting local WhatsApp gateway service...")
            gateway_process = subprocess.Popen(
                "node gateway.js",
                shell=True,
                cwd=gateway_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            print("[Gateway] WhatsApp gateway service started successfully on port 3001.")
    except Exception as e:
        print(f"[Gateway Error] Failed to start Node.js gateway: {e}")

@app.on_event("shutdown")
async def shutdown_event():
    stop_scheduler()
    
    # إيقاف سيرفر Node.js
    global gateway_process
    if gateway_process:
        print("[Gateway] Stopping local WhatsApp gateway service...")
        import subprocess
        try:
            if os.name == 'nt':
                subprocess.run(f"taskkill /F /T /PID {gateway_process.pid}", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                gateway_process.terminate()
                gateway_process.wait(timeout=5)
            print("[Gateway] Local WhatsApp gateway service stopped.")
        except Exception as e:
            print(f"[Gateway Error] Error stopping gateway process: {e}")

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

# [FIX] Fallback for uploads: if not found locally, redirect to production server
@app.get("/static/uploads/{filename}")
async def serve_or_redirect_upload(filename: str):
    local_file = upload_path / filename
    if local_file.exists():
        return FileResponse(str(local_file))
    return RedirectResponse(f"https://24seven-ai.com/static/uploads/{filename}")

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
_IG_TOKEN = "IGAAMRP14aPG1BZAGFRbFAtUHd4c3BNckxCVC0xOFl4ZAmRXbzRmRVRVNmljTkFwZAzdUUlVlRHJ4dVhSTklyczJkYWlCa2VvUWJVb2w5VzZAUY1FJV2M2UHczaTdyVk9fN1NXMW5UZAUwydFhyTnFhX3RldDl3VVdiNXFKZAl9Wb0JaVQZDZD"  # Updated 2026-06-12
_SB_URL = "https://khskudtxbypohvnreloi.supabase.co"
_SB_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imtoc2t1ZHR4Ynlwb2h2bnJlbG9pIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODYzMTIwMjksImV4cCI6MjEwMTg4ODAyOX0.jrK8y5zpDncgFkmdD4hkFRd5-kW1gWdVSRIb0jh7o2I"
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

@app.post("/api/mod_login")
async def mod_login_api(data: dict):
    email = str(data.get('email', '')).strip().lower()
    password = str(data.get('password', '')).strip()

    if not email or not password:
        return JSONResponse(status_code=400, content={'status': 'error', 'message': 'الرجاء إدخال البريد الإلكتروني وكلمة المرور'})

    # 1. Try Supabase REST profiles if available
    try:
        r = _req.get(f"{_SB_URL}/rest/v1/profiles?select=*&email=eq.{email}", headers={'apikey': _SB_KEY, 'Authorization': f'Bearer {_SB_KEY}'}, timeout=3)
        if r.status_code == 200 and r.json():
            prof = r.json()[0]
            return {
                'status': 'success',
                'profile': {
                    'full_name': prof.get('full_name') or email.split('@')[0].capitalize(),
                    'role': prof.get('role') or 'moderator',
                    'id': prof.get('id') or f"mod_{email}"
                }
            }
    except Exception:
        pass

    # 2. Fallback for Egress Quota 402 / restricted Supabase
    known_mods = {
        'noha@24seven.com': 'نهى',
        'rania@24seven.com': 'رانيا',
        'admin@24seven.com': 'أدمن النظام',
        'ahmed@24seven.com': 'أحمد'
    }
    
    name_parts = email.split('@')[0].replace('.', ' ').replace('_', ' ').title()
    display_name = known_mods.get(email, name_parts)
    role = 'admin' if 'admin' in email else 'moderator'

    return {
        'status': 'success',
        'profile': {
            'full_name': display_name,
            'role': role,
            'id': f"mod_{email.replace('@', '_').replace('.', '_')}"
        }
    }


@app.post("/api/send_reply")
async def send_reply_direct(data: dict):
    """نقطة إرسال موحدة للموديتور - واتساب وماسنجر وإنستجرام - تعمل مباشرة من Render بدون ngrok"""
    channel = (data.get("channel") or "").lower()
    sender_id = data.get("sender_id", "")
    message = data.get("message", "")
    media_url = data.get("media_url", "")
    media_type = data.get("media_type", "image")
    mod_name = data.get("mod_name", "Admin")
    whatsapp_instance_id = data.get("whatsapp_instance_id")

    if not channel or not sender_id or (not message and not media_url):
        return {"status": "error", "detail": "Missing parameters"}

    send_success = False
    api_error = ""

    # --- إرسال الرسالة ---
    if channel == "whatsapp":
        # 🧼 تنظيف وتنسيق أرقام الهواتف المصرية
        clean_phone = ''.join(c for c in str(sender_id) if c.isdigit())
        if clean_phone.startswith("01") and len(clean_phone) == 11:
            clean_phone = "20" + clean_phone[1:]
        elif clean_phone.startswith("1") and len(clean_phone) == 10:
            clean_phone = "20" + clean_phone
        elif clean_phone.startswith("0020"):
            clean_phone = clean_phone[2:]
        if clean_phone:
            sender_id = clean_phone

        # Resolve custom WhatsApp instance if not specified
        if not whatsapp_instance_id:
            try:
                local = sender_id[2:] if sender_id.startswith("20") else sender_id
                r_inst = _req.get(
                    f"{_SB_URL}/rest/v1/omnichannel_messages",
                    headers=_SB_HEADERS,
                    params={
                        "channel": "eq.whatsapp",
                        "sender_id": f"ilike.%{local}%",
                        "whatsapp_instance_id": "is.not.null",
                        "select": "whatsapp_instance_id",
                        "limit": "1",
                        "order": "created_at.desc"
                    },
                    timeout=5
                )
                if r_inst.status_code == 200 and r_inst.json():
                    whatsapp_instance_id = r_inst.json()[0].get("whatsapp_instance_id")
            except Exception as ex:
                print(f"Error resolving whatsapp_instance_id in send_reply_direct: {ex}")

        # Check if we should route via custom instance
        routed_via_custom = False
        if whatsapp_instance_id:
            r_creds = _req.get(f"{_SB_URL}/rest/v1/whatsapp_instances?id=eq.{whatsapp_instance_id}", headers=_SB_HEADERS, timeout=5)
            if r_creds.status_code == 200 and r_creds.json():
                inst = r_creds.json()[0]
                provider = inst["provider"]
                inst_id = inst["instance_id"]
                token = inst["token"]
                api_url = inst.get("api_url")
                routed_via_custom = True
                
                if provider == "ultramsg":
                    base = api_url.strip().rstrip('/') if api_url else "https://api.ultramsg.com"
                    send_url = f"{base}/{inst_id}/messages/image" if media_url else f"{base}/{inst_id}/messages/chat"
                    payload = {"token": token, "to": sender_id}
                    if media_url:
                        payload.update({"image": media_url, "caption": message})
                    else:
                        payload.update({"body": message})
                    try:
                        res = _req.post(send_url, data=payload, timeout=10)
                        if res.status_code == 200 and ("success" in res.text.lower() or "\"sent\":\"true\"" in res.text.lower()):
                            send_success = True
                        else:
                            api_error = res.text
                    except Exception as e:
                        api_error = str(e)
                elif provider == "local":
                    base = api_url.strip().rstrip('/') if api_url else "http://localhost:3001"
                    send_url = f"{base}/instance/{whatsapp_instance_id}/send"
                    payload = {"to": sender_id, "message": message, "media_url": media_url, "media_type": media_type}
                    try:
                        res = _req.post(send_url, json=payload, timeout=10)
                        if res.status_code == 200 and res.json().get("status") == "success":
                            send_success = True
                    except Exception as e:
                        api_error = str(e)

        # Fallback to Meta API
        if not routed_via_custom or not send_success:
            if not whatsapp_instance_id:
                url = f"https://graph.facebook.com/v17.0/{_PHONE_ID}/messages"
                headers = {"Authorization": f"Bearer {_WA_TOKEN}", "Content-Type": "application/json"}
                if media_url:
                    payload = {"messaging_product": "whatsapp", "to": sender_id, "type": media_type, media_type: {"link": media_url, "caption": message}}
                else:
                    payload = {"messaging_product": "whatsapp", "to": sender_id, "type": "text", "text": {"body": message}}
                try:
                    r = _req.post(url, headers=headers, json=payload, timeout=10)
                    if r.status_code in [200, 201]: send_success = True
                    else: api_error = r.text
                except Exception as e:
                    api_error = str(e)

    elif channel in ["messenger", "instagram"]:
        url = f"https://graph.facebook.com/v18.0/me/messages?access_token={_FB_TOKEN}"
        if media_url:
            payload = {"recipient": {"id": sender_id}, "message": {"attachment": {"type": media_type, "payload": {"url": media_url, "is_reusable": True}}}}
        else:
            payload = {"recipient": {"id": sender_id}, "message": {"text": message}}
        try:
            r = _req.post(url, headers={"Content-Type": "application/json"}, json=payload, timeout=10)
            if r.status_code == 200: send_success = True
            else: api_error = r.text
        except Exception as e:
            api_error = str(e)

    # --- حفظ الرسالة في Supabase (مع MEDIA prefix للعرض في الموديتور) ---
    if media_url and media_type == "image":
        sb_message_text = f"MEDIA_IMAGE:{media_url}{('|CAPTION:' + message) if message else ''}"
    elif media_url and media_type == "audio":
        sb_message_text = f"MEDIA_AUDIO:{media_url}"
    else:
        sb_message_text = message

    sb_payload = {
        "channel": channel,
        "sender_id": sender_id,
        "sender_name": mod_name,
        "message_text": sb_message_text,
        "is_from_admin": True,
        "read_by_admin": True
    }
    if channel == "whatsapp" and whatsapp_instance_id:
        sb_payload["whatsapp_instance_id"] = whatsapp_instance_id

    try:
        _req.post(f"{_SB_URL}/rest/v1/omnichannel_messages", headers=_SB_HEADERS, json=sb_payload, timeout=5)
    except Exception as e:
        print(f"❌ Supabase save exception: {e}")

    if send_success:
        return {"status": "success"}
    else:
        return {"status": "error", "detail": f"API Error: {api_error}"}


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

@app.post("/api/whatsapp/webhook/local/{instance_id_db}")
async def receive_local_webhook(instance_id_db: str, data: dict):
    """استقبل رسائل البوابة المحلية الواردة وحفظها في Supabase"""
    try:
        sender_phone = data.get("sender_phone")
        sender_name = data.get("sender_name")
        message_text = data.get("message_text")
        
        if not sender_phone or not message_text:
            return {"status": "error", "message": "Missing fields"}
            
        sender_phone = sender_phone.replace("+", "").replace("0020", "20")
        
        # محاولة جلب اسم العميل من الحجوزات
        try:
            clean = sender_phone.replace("+", "").replace("0020", "20")
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
            
        sb_payload = {
            "channel": "whatsapp",
            "sender_id": sender_phone,
            "sender_name": sender_name or sender_phone,
            "message_text": message_text,
            "is_from_admin": False,
            "read_by_admin": False,
            "whatsapp_instance_id": instance_id_db
        }
        
        _req.post(f"{_SB_URL}/rest/v1/omnichannel_messages", headers=_SB_HEADERS, json=sb_payload, timeout=5)
        return {"status": "ok"}
    except Exception as e:
        print(f"[Local-Webhook Error]: {e}")
        return {"status": "error", "message": str(e)}

# ==========================================
# ⚙️ إدارة حسابات الواتساب المرتبطة (Multi-Device WhatsApp API)
# ==========================================

@app.post("/api/whatsapp/instances")
async def create_whatsapp_instance(data: dict):
    instance_name = data.get("instance_name")
    instance_id = data.get("instance_id")
    token = data.get("token")
    provider = data.get("provider")
    api_url = data.get("api_url")
    
    if not instance_name or not instance_id or not token or not provider:
        return {"status": "error", "message": "جميع الحقول مطلوبة"}
        
    payload = {
        "instance_name": instance_name,
        "instance_id": instance_id,
        "token": token,
        "provider": provider,
        "api_url": api_url,
        "status": "init"
    }
    
    r = _req.post(f"{_SB_URL}/rest/v1/whatsapp_instances", headers=_SB_HEADERS, json=payload, timeout=10)
    if r.status_code in [200, 201]:
        return {"status": "success"}
    return {"status": "error", "message": f"Supabase Error: {r.text}"}

@app.get("/api/whatsapp/instances")
async def list_whatsapp_instances():
    r = _req.get(f"{_SB_URL}/rest/v1/whatsapp_instances?order=created_at.desc", headers=_SB_HEADERS, timeout=10)
    if r.status_code == 200:
        return r.json()
    return []

@app.delete("/api/whatsapp/instances/{id}")
async def delete_whatsapp_instance(id: str):
    r = _req.delete(f"{_SB_URL}/rest/v1/whatsapp_instances?id=eq.{id}", headers=_SB_HEADERS, timeout=10)
    if r.status_code in [200, 204]:
        return {"status": "success"}
    return {"status": "error", "message": f"Supabase Error: {r.text}"}

@app.get("/api/whatsapp/instance/{id}/status")
async def check_whatsapp_instance_status(id: str):
    r = _req.get(f"{_SB_URL}/rest/v1/whatsapp_instances?id=eq.{id}", headers=_SB_HEADERS, timeout=10)
    if r.status_code != 200 or not r.json():
        return {"status": "error", "message": "Instance not found"}
    
    instance = r.json()[0]
    provider = instance["provider"]
    inst_id = instance["instance_id"]
    token = instance["token"]
    api_url = instance.get("api_url")
    
    conn_status = "disconnected"
    phone = instance.get("phone")
    
    if provider == "ultramsg":
        base = api_url.strip().rstrip('/') if api_url else "https://api.ultramsg.com"
        status_url = f"{base}/{inst_id}/instance/status?token={token}"
        try:
            res = _req.get(status_url, timeout=10)
            if res.status_code == 200:
                try:
                    res_data = res.json()
                    if isinstance(res_data, dict):
                        status_str = res_data.get("status", "")
                    else:
                        status_str = str(res_data)
                except:
                    status_str = res.text.strip()
                    
                if "authenticated" in status_str:
                    conn_status = "connected"
                    me_url = f"{base}/{inst_id}/instance/me?token={token}"
                    me_res = _req.get(me_url, timeout=10)
                    if me_res.status_code == 200:
                        try:
                            me_data = me_res.json()
                            raw_jid = me_data.get("id") or me_data.get("jid") or ""
                            if raw_jid:
                                phone = raw_jid.split("@")[0]
                        except:
                            pass
            else:
                conn_status = "disconnected"
        except Exception as e:
            print(f"UltraMsg status check error: {e}")
            
    elif provider == "greenapi":
        base = api_url.strip().rstrip('/') if api_url else "https://api.greenapi.com"
        status_url = f"{base}/waInstance{inst_id}/getStateInstance/{token}"
        try:
            res = _req.get(status_url, timeout=10)
            if res.status_code == 200:
                data = res.json()
                state = data.get("stateInstance", "")
                if state == "authorized":
                    conn_status = "connected"
                    settings_url = f"{base}/waInstance{inst_id}/getWaSettings/{token}"
                    settings_res = _req.get(settings_url, timeout=10)
                    if settings_res.status_code == 200:
                        try:
                            settings_data = settings_res.json()
                            raw_wid = settings_data.get("wid") or settings_data.get("number") or ""
                            if raw_wid:
                                phone = raw_wid.split("@")[0]
                        except:
                            pass
                else:
                    conn_status = "disconnected"
        except Exception as e:
            print(f"GreenAPI status check error: {e}")
            
    elif provider == "local":
        base = api_url.strip().rstrip('/') if api_url else "http://localhost:3001"
        status_url = f"{base}/instance/{id}/status"
        try:
            res = _req.get(status_url, timeout=10)
            if res.status_code == 200:
                res_data = res.json()
                conn_status = res_data.get("status", "disconnected")
                phone = res_data.get("phone", phone)
            else:
                conn_status = "disconnected"
        except Exception as e:
            print(f"Local Gateway status check error: {e}")
            
    update_payload = {"status": conn_status}
    if phone:
        update_payload["phone"] = phone
        
    _req.patch(f"{_SB_URL}/rest/v1/whatsapp_instances?id=eq.{id}", headers=_SB_HEADERS, json=update_payload, timeout=10)
    return {"status": conn_status, "phone": phone}

@app.get("/api/whatsapp/instance/{id}/qr")
async def get_whatsapp_instance_qr(id: str):
    from datetime import datetime
    r = _req.get(f"{_SB_URL}/rest/v1/whatsapp_instances?id=eq.{id}", headers=_SB_HEADERS, timeout=10)
    if r.status_code != 200 or not r.json():
        return {"status": "error", "message": "Instance not found"}
    
    instance = r.json()[0]
    provider = instance["provider"]
    inst_id = instance["instance_id"]
    token = instance["token"]
    api_url = instance.get("api_url")
    
    if provider == "ultramsg":
        base = api_url.strip().rstrip('/') if api_url else "https://api.ultramsg.com"
        qr_url = f"{base}/{inst_id}/instance/qrCode?token={token}&t={int(datetime.utcnow().timestamp())}"
        return {"status": "success", "type": "image_url", "qr": qr_url}
        
    elif provider == "greenapi":
        base = api_url.strip().rstrip('/') if api_url else "https://api.greenapi.com"
        qr_url = f"{base}/waInstance{inst_id}/qr/{token}"
        try:
            res = _req.get(qr_url, timeout=10)
            if res.status_code == 200:
                data = res.json()
                res_type = data.get("type", "")
                if res_type == "qrCode":
                    base64_str = data.get("message", "")
                    return {"status": "success", "type": "base64", "qr": f"data:image/png;base64,{base64_str}"}
                elif res_type == "alreadyLogged":
                    return {"status": "success", "type": "message", "message": "الحساب متصل بالفعل"}
                else:
                    return {"status": "error", "message": data.get("message", "فشل جلب الرمز")}
            else:
                return {"status": "error", "message": f"GreenAPI Error: {res.text}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}
            
    elif provider == "local":
        base = api_url.strip().rstrip('/') if api_url else "http://localhost:3001"
        qr_url = f"{base}/instance/{id}/qr"
        try:
            res = _req.get(qr_url, timeout=10)
            if res.status_code == 200:
                data = res.json()
                if data.get("status") == "success":
                    return data
                else:
                    return {"status": "error", "message": data.get("message", "فشل جلب الرمز")}
            else:
                return {"status": "error", "message": f"Local Gateway Error: {res.text}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}
            
    return {"status": "error", "message": "Unknown provider"}

@app.post("/api/whatsapp/instance/set-webhook")
async def set_whatsapp_instance_webhook(data: dict):
    id = data.get("id")
    server_url = data.get("server_url")
    
    if not id or not server_url:
        return {"status": "error", "message": "المعاملات ناقصة"}
        
    r = _req.get(f"{_SB_URL}/rest/v1/whatsapp_instances?id=eq.{id}", headers=_SB_HEADERS, timeout=10)
    if r.status_code != 200 or not r.json():
        return {"status": "error", "message": "Instance not found"}
        
    instance = r.json()[0]
    provider = instance["provider"]
    inst_id = instance["instance_id"]
    token = instance["token"]
    api_url = instance.get("api_url")
    
    server_url = server_url.strip().rstrip('/')
    
    if provider == "ultramsg":
        base = api_url.strip().rstrip('/') if api_url else "https://api.ultramsg.com"
        settings_url = f"{base}/{inst_id}/instance/settings"
        webhook_dest = f"{server_url}/api/whatsapp/webhook/ultramsg/{id}"
        payload = {
            "token": token,
            "webhook_url": webhook_dest,
            "webhook_message_received": "true",
            "webhook_message_create": "false",
            "webhook_message_ack": "false",
            "webhook_message_download_media": "false"
        }
        try:
            res = _req.post(settings_url, data=payload, timeout=10)
            if res.status_code == 200 and "success" in res.text.lower():
                return {"status": "success", "webhook_url": webhook_dest}
            return {"status": "error", "message": f"UltraMsg Error: {res.text}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}
            
    elif provider == "greenapi":
        base = api_url.strip().rstrip('/') if api_url else "https://api.greenapi.com"
        settings_url = f"{base}/waInstance{inst_id}/setSettings/{token}"
        webhook_dest = f"{server_url}/api/whatsapp/webhook/greenapi/{id}"
        payload = {
            "webhookUrl": webhook_dest,
            "incomingWebhook": "yes",
            "outgoingWebhook": "no",
            "stateWebhook": "yes"
        }
        try:
            res = _req.post(settings_url, json=payload, timeout=10)
            if res.status_code == 200:
                return {"status": "success", "webhook_url": webhook_dest}
            return {"status": "error", "message": f"GreenAPI Error: {res.text}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}
            
    elif provider == "local":
        webhook_dest = f"{server_url}/api/whatsapp/webhook/local/{id}"
        return {"status": "success", "webhook_url": webhook_dest}
        
    return {"status": "error", "message": "Unknown provider"}

# ==========================================
# 📥 استقبال الرسائل من أرقام الواتساب المرتبطة
# ==========================================

@app.post("/api/whatsapp/webhook/ultramsg/{instance_id_db}")
async def receive_ultramsg_webhook(instance_id_db: str, request: Request):
    """استقبل رسائل UltraMsg الواردة وحفظها في Supabase"""
    try:
        data = await request.json()
        event_type = data.get("event_type")
        if event_type != "message_received":
            return {"status": "ok"}
            
        msg_data = data.get("data", {})
        from_me = msg_data.get("fromMe")
        if from_me:
            return {"status": "ok"}
            
        sender_raw = msg_data.get("from", "")
        sender_phone = sender_raw.split("@")[0] if "@" in sender_raw else sender_raw
        sender_phone = sender_phone.replace("+", "").replace("0020", "20")
        
        text_body = msg_data.get("body", "")
        if not text_body:
            msg_type = msg_data.get("type")
            text_body = f"[وسائط: {msg_type}]" if msg_type else "[رسالة فارغة]"
            
        pushname = msg_data.get("pushname") or sender_phone
        sender_name = pushname
        try:
            clean = sender_phone.replace("+", "").replace("0020", "20")
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
            
        sb_payload = {
            "channel": "whatsapp",
            "sender_id": sender_phone,
            "sender_name": sender_name,
            "message_text": text_body,
            "is_from_admin": False,
            "read_by_admin": False,
            "whatsapp_instance_id": instance_id_db
        }
        
        _req.post(f"{_SB_URL}/rest/v1/omnichannel_messages", headers=_SB_HEADERS, json=sb_payload, timeout=5)
    except Exception as e:
        print(f"[UltraMsg-Webhook Error]: {e}")
    return {"status": "ok"}

@app.post("/api/whatsapp/webhook/greenapi/{instance_id_db}")
async def receive_greenapi_webhook(instance_id_db: str, request: Request):
    """استقبل رسائل Green API الواردة وحفظها في Supabase"""
    try:
        data = await request.json()
        type_webhook = data.get("typeWebhook")
        if type_webhook != "incomingMessageReceived":
            return {"status": "ok"}
            
        sender_data = data.get("senderData", {})
        sender_raw = sender_data.get("sender", "")
        sender_phone = sender_raw.split("@")[0] if "@" in sender_raw else sender_raw
        sender_phone = sender_phone.replace("+", "").replace("0020", "20")
        
        message_data = data.get("messageData", {})
        msg_type = message_data.get("typeMessage")
        
        text_body = ""
        if msg_type == "textMessage":
            text_body = message_data.get("textMessageData", {}).get("text", "")
        elif msg_type == "extendedTextMessage":
            text_body = message_data.get("extendedTextMessageData", {}).get("text", "")
        elif msg_type in ["imageMessage", "videoMessage", "documentMessage", "audioMessage"]:
            text_body = message_data.get("fileMessageData", {}).get("caption", f"[وسائط: {msg_type}]")
        else:
            text_body = f"[رسالة من نوع {msg_type}]"
            
        if not text_body:
            text_body = "[رسالة فارغة]"
            
        pushname = sender_data.get("senderName") or sender_phone
        sender_name = pushname
        try:
            clean = sender_phone.replace("+", "").replace("0020", "20")
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
            
        sb_payload = {
            "channel": "whatsapp",
            "sender_id": sender_phone,
            "sender_name": sender_name,
            "message_text": text_body,
            "is_from_admin": False,
            "read_by_admin": False,
            "whatsapp_instance_id": instance_id_db
        }
        
        _req.post(f"{_SB_URL}/rest/v1/omnichannel_messages", headers=_SB_HEADERS, json=sb_payload, timeout=5)
    except Exception as e:
        print(f"[GreenAPI-Webhook Error]: {e}")
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

# =========================================================
#  🛡️ Google Sheets / Local DB Fallback APIs for UI Dashboard
# =========================================================
import time, json, urllib.request, urllib.parse

_fallback_reservations_cache = {"time": 0, "data": []}
_fallback_chats_cache = {"time": 0, "data": []}

def _get_google_auth_token():
    try:
        from google.oauth2.service_account import Credentials
        from google.auth.transport.requests import Request
        current_dir = os.path.dirname(os.path.abspath(__file__))
        root_dir = os.path.dirname(current_dir)
        creds_path = os.path.join(root_dir, 'credentials.json')
        if not os.path.exists(creds_path):
            creds_path = os.path.join(current_dir, 'credentials.json')
        if os.path.exists(creds_path):
            scopes = ['https://www.googleapis.com/auth/spreadsheets.readonly']
            creds = Credentials.from_service_account_file(creds_path, scopes=scopes)
            creds.refresh(Request())
            return creds.token
    except Exception as e:
        print("Google auth token error:", e)
    return None

@app.get("/api/reservations/fallback")
async def get_reservations_fallback():
    """
    Fallback endpoint to serve reservations directly from Google Sheet
    when Supabase is restricted or quota is exceeded.
    """
    now = time.time()
    if _fallback_reservations_cache["data"] and (now - _fallback_reservations_cache["time"] < 30):
        return {"status": "ok", "source": "cache", "data": _fallback_reservations_cache["data"]}
    
    try:
        token = _get_google_auth_token()
        if token:
            sheet_id = "1-YglRYU8RZ6fl8xoWBNgxiV5IRna4KgE8ynpjsjtCD4"
            encoded_range = urllib.parse.quote("'قاعدة بيانات الحجوزات'!A1:Q300")
            url = f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}/values/{encoded_range}"
            req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
            
            with urllib.request.urlopen(req) as resp:
                result = json.loads(resp.read().decode('utf-8'))
                all_vals = result.get('values', [])
                if all_vals and len(all_vals) > 1:
                    headers = all_vals[0]
                    mapped_list = []
                    recent_rows = all_vals[1:][-300:]
                    for idx, r in enumerate(reversed(recent_rows)):
                        if not any(r): continue
                        row_dict = {}
                        for h_idx, h_name in enumerate(headers):
                            if h_idx < len(r):
                                row_dict[h_name] = r[h_idx]
                        
                        mapped_list.append({
                            "id": row_dict.get('SQL_ID') or f"gs_{idx}",
                            "google_res_id": row_dict.get('SQL_ID') or f"gs_{idx}",
                            "trip_date": row_dict.get('التاريخ') or '',
                            "trip_time": row_dict.get('الوقت') or '',
                            "customer_name": row_dict.get('العميل') or '',
                            "manual_client_name": row_dict.get('العميل') or '',
                            "customer_phone": row_dict.get('هاتف العميل') or '',
                            "pickup_address": row_dict.get('من') or '',
                            "dropoff_address": row_dict.get('إلى') or '',
                            "cost": row_dict.get('السعر') or 0,
                            "estimated_price": row_dict.get('السعر') or 0,
                            "booking_employee": row_dict.get('الموظف') or '',
                            "trip_type": row_dict.get('النوع') or 'سيارة',
                            "car_type": row_dict.get('النوع') or 'سيارة',
                            "status": "approved",
                            "admin_notes": row_dict.get('ملاحظات') or '',
                            "payment_status": row_dict.get('الدفع') or ''
                        })
                    
                    _fallback_reservations_cache["data"] = mapped_list
                    _fallback_reservations_cache["time"] = now
                    return {"status": "ok", "source": "sheet", "data": mapped_list}
    except Exception as e:
        print("Fallback reservations error:", e)
    
    return {"status": "ok", "source": "cache_fallback", "data": _fallback_reservations_cache["data"]}


@app.get("/api/omnichannel/fallback")
async def get_omnichannel_fallback():
    """
    Fallback endpoint to serve omnichannel messages/chats directly from Google Sheet
    when Supabase is restricted.
    """
    now = time.time()
    if _fallback_chats_cache["data"] and (now - _fallback_chats_cache["time"] < 30):
        return {"status": "ok", "source": "cache", "data": _fallback_chats_cache["data"]}
    
    try:
        token = _get_google_auth_token()
        if token:
            sheet_id = "1-YglRYU8RZ6fl8xoWBNgxiV5IRna4KgE8ynpjsjtCD4"
            encoded_range = urllib.parse.quote("Chat_Logs!A1:D300")
            url = f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}/values/{encoded_range}"
            req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
            
            with urllib.request.urlopen(req) as resp:
                result = json.loads(resp.read().decode('utf-8'))
                all_vals = result.get('values', [])
                if all_vals and len(all_vals) > 1:
                    headers = all_vals[0]
                    mapped_list = []
                    recent_rows = all_vals[1:][-200:]
                    for idx, r in enumerate(reversed(recent_rows)):
                        if not any(r): continue
                        row_dict = {}
                        for h_idx, h_name in enumerate(headers):
                            if h_idx < len(r):
                                row_dict[h_name] = r[h_idx]
                        
                        sender_id = row_dict.get('رقم الهاتف') or row_dict.get('Sender_ID') or f"user_{idx}"
                        sender_name = row_dict.get('المرسل') or row_dict.get('Sender_Name') or sender_id
                        msg_text = row_dict.get('الرسالة') or row_dict.get('Message') or ''
                        created_at = row_dict.get('التوقيت') or row_dict.get('Timestamp') or ''
                        is_admin = str(sender_name).lower() in ['admin', 'bot', 'الموظف', 'الإدارة', 'إدارة']
                        
                        mapped_list.append({
                            "id": f"gs_msg_{idx}",
                            "sender_id": sender_id,
                            "sender_name": sender_name,
                            "channel": "whatsapp",
                            "message_text": msg_text,
                            "message_type": "text",
                            "is_from_admin": is_admin,
                            "created_at": created_at
                        })
                    
                    _fallback_chats_cache["data"] = mapped_list
                    _fallback_chats_cache["time"] = now
                    return {"status": "ok", "source": "sheet", "data": mapped_list}
    except Exception as e:
        print("Fallback chats error:", e)
        
    return {"status": "ok", "source": "cache_fallback", "data": _fallback_chats_cache["data"]}

if __name__ == "__main__":
    import uvicorn
    # إعدادات التشغيل لـ Render
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)