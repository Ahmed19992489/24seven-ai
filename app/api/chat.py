from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from app import models, database
from app.api.auth import get_current_user
from pydantic import BaseModel
import requests
import json
import traceback

router = APIRouter()

# =====================================================
# 🔑 إعدادات الواتساب والماسنجر و Supabase
# =====================================================
WHATSAPP_TOKEN = "EAAPDbwUyvY0BQrm6ZB9qb62LU9hI50ZC9QOfZAO3VPA7ZCSnFSRMCb2kouBRkXu4LiVmRU2ydv1vLl00kKmgTFMN5ULJOpImor7i8oITjicjIjWiOLxTL7yltYrlF0RLxcdU6UNOaIdqo4Ouv0BnQ79OK2sgSLpHY9ZCQs4iRIxcpjnoxr8EWpV4FSgGTzgZDZD"
PHONE_ID = "597129733493778"
FB_PAGE_TOKEN = "EAAPDbwUyvY0BQ3KLTieXWMHZAJZC92eQI9sBwEISipvaaVR9hoteMHWhx0fi8mSXIC4TnTiBHpykmsv6HyAkYK4yQUyQv81ZCF7EZA5CEZAKwPqhfl3jjmaN5muRSk1ZCpNh7OXAQ8Ey7ilMhBmjPvQpLRlzMD8MbYWChOdFxwiFKgPNAqJhg6aVZBR25rvIvChgw1vusjBwHZAeveEMSHpaQ9ps"
INSTAGRAM_TOKEN = "IGAAMRP14aPG1BZAGFRbFAtUHd4c3BNckxCVC0xOFl4ZAmRXbzRmRVRVNmljTkFwZAzdUUlVlRHJ4dVhSTklyczJkYWlCa2VvUWJVb2w5VzZAUY1FJV2M2UHczaTdyVk9fN1NXMW5UZAUwydFhyTnFhX3RldDl3VVdiNXFKZAl9Wb0JaVQZDZD"  # Updated 2026-06-12

SUPABASE_URL = 'https://wtjwzqvmwnbvjxnmweqq.supabase.co'
SUPABASE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Ind0and6cXZtd25idmp4bm13ZXFxIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzE0NjU0MDMsImV4cCI6MjA4NzA0MTQwM30.kTFK22b18cc1BmvMyLTt-7V113jyf_YrodSB7Km00tY'
SUPABASE_HEADERS = {
    'apikey': SUPABASE_KEY,
    'Authorization': f'Bearer {SUPABASE_KEY}',
    'Content-Type': 'application/json'
}

# --- نماذج البيانات (Pydantic Models) ---

class MessageCreate(BaseModel):
    message: str

class AdminReply(BaseModel):
    user_id: int
    message: str

class MessageResponse(BaseModel):
    id: int
    message: str
    sender: str
    created_at: datetime

    class Config:
        from_attributes = True

class OmnichannelReply(BaseModel):
    channel: str # 'whatsapp', 'messenger', or 'instagram'
    sender_id: str
    message: str
    whatsapp_instance_id: Optional[str] = None

# --- نقاط الاتصال (Endpoints) ---

@router.post("/send", response_model=MessageResponse)
async def send_message(
    data: MessageCreate, 
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user)
):
    """يستخدمها العميل لإرسال رسالة للدعم الفني"""
    new_msg = models.ChatMessage(
        user_id=current_user.id,
        message=data.message,
        sender="user"
    )
    db.add(new_msg)
    db.commit()
    db.refresh(new_msg)
    return new_msg

@router.get("/history", response_model=List[MessageResponse])
async def get_chat_history(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user)
):
    """يستخدمها العميل لجلب محادثته الخاصة مع الدعم"""
    messages = db.query(models.ChatMessage).filter(
        models.ChatMessage.user_id == current_user.id
    ).order_by(models.ChatMessage.created_at.asc()).all()
    return messages

@router.get("/admin/all-chats")
async def get_admin_chats(db: Session = Depends(database.get_db)):
    """يستخدمها المدير لرؤية قائمة العملاء الذين أرسلوا رسائل في القائمة الجانبية"""
    # جلب المستخدمين الذين لديهم رسائل فقط
    users_with_msgs = db.query(models.User).join(models.ChatMessage).distinct().all()
    
    result = []
    for user in users_with_msgs:
        last_msg = db.query(models.ChatMessage).filter(
            models.ChatMessage.user_id == user.id
        ).order_by(models.ChatMessage.created_at.desc()).first()
        
        if last_msg:
            result.append({
                "user_id": user.id,
                "user_email": user.email,
                "last_message": last_msg.message,
                "timestamp": last_msg.created_at
            })
    return result

@router.get("/history-admin/{user_id}", response_model=List[MessageResponse])
async def get_chat_history_for_admin(user_id: int, db: Session = Depends(database.get_db)):
    """
    ✅ الحل النهائي لخطأ 404: 
    الدالة المسؤولة عن عرض الرسائل في المربع الكبير للمدير عند اختيار عميل معين.
    هذا المسار يضمن استرجاع كافة الرسائل الخاصة بمستخدم محدد لعرضها للإدارة.
    """
    messages = db.query(models.ChatMessage).filter(
        models.ChatMessage.user_id == user_id
    ).order_by(models.ChatMessage.created_at.asc()).all()
    
    if not messages:
        # إذا لم توجد رسائل، نعيد قائمة فارغة بدل الخطأ لضمان استقرار الواجهة
        return []
        
    return messages

@router.post("/admin/reply")
async def admin_reply(data: AdminReply, db: Session = Depends(database.get_db)):
    """يستخدمها المدير للرد على عميل معين من داخل لوحة التحكم"""
    new_msg = models.ChatMessage(
        user_id=data.user_id,
        message=data.message,
        sender="admin"
    )
    db.add(new_msg)
    db.commit()
    return {"status": "success", "message": "Reply sent successfully"}

# =====================================================
# 🚀 API صندوق الوارد الموحد (Omnichannel Inbox)
# =====================================================
@router.post("/send_omnichannel")
async def send_omnichannel_reply(
    data: OmnichannelReply, 
    # Depends(get_current_user) is omitted here for simplicity while migrating, ensuring the admin CRM works directly
):
    """
    تقوم هذه الدالة بإرسال رسالة من الموظف للعميل بناءً على القناة المستخدمة (WhatsApp أو Messenger أو Instagram)
    ثم تحفظ الرسالة في Supabase
    """
    channel = data.channel.lower()
    whatsapp_instance_id = data.whatsapp_instance_id
    
    send_success = False
    api_error = ""

    # 1. إرسال الرسالة عبر القناة المناسبة
    if channel == 'whatsapp':
        # Resolve custom WhatsApp instance if not specified
        if not whatsapp_instance_id:
            try:
                clean_phone = data.sender_id.replace("+", "").replace("0020", "20")
                local = clean_phone[2:] if clean_phone.startswith("20") else clean_phone
                r_inst = requests.get(
                    f"{SUPABASE_URL}/rest/v1/omnichannel_messages",
                    headers=SUPABASE_HEADERS,
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
                print(f"Error resolving whatsapp_instance_id in send_omnichannel: {ex}")

        # Check if we should route via custom instance
        routed_via_custom = False
        if whatsapp_instance_id:
            r_creds = requests.get(f"{SUPABASE_URL}/rest/v1/whatsapp_instances?id=eq.{whatsapp_instance_id}", headers=SUPABASE_HEADERS, timeout=5)
            if r_creds.status_code == 200 and r_creds.json():
                inst = r_creds.json()[0]
                provider = inst["provider"]
                inst_id = inst["instance_id"]
                token = inst["token"]
                api_url = inst.get("api_url")
                routed_via_custom = True
                
                if provider == "ultramsg":
                    base = api_url.strip().rstrip('/') if api_url else "https://api.ultramsg.com"
                    send_url = f"{base}/{inst_id}/messages/chat"
                    payload = {
                        "token": token,
                        "to": data.sender_id,
                        "body": data.message
                    }
                    try:
                        res = requests.post(send_url, data=payload, timeout=10)
                        if res.status_code == 200 and ("success" in res.text.lower() or "\"sent\":\"true\"" in res.text.lower()):
                            send_success = True
                        else:
                            api_error = res.text
                            print(f"❌ UltraMsg send failed in chat.py: {res.text}")
                    except Exception as e:
                        api_error = str(e)
                        print(f"❌ UltraMsg exception in chat.py: {e}")
                elif provider == "greenapi":
                    base = api_url.strip().rstrip('/') if api_url else "https://api.greenapi.com"
                    send_url = f"{base}/waInstance{inst_id}/sendMessage/{token}"
                    clean_num = data.sender_id.replace("+", "").replace("0020", "20")
                    payload = {
                        "chatId": f"{clean_num}@c.us",
                        "message": data.message
                    }
                    try:
                        res = requests.post(send_url, json=payload, timeout=10)
                        if res.status_code == 200:
                            send_success = True
                        else:
                            api_error = res.text
                            print(f"❌ GreenAPI send failed in chat.py: {res.text}")
                    except Exception as e:
                        api_error = str(e)
                        print(f"❌ GreenAPI exception in chat.py: {e}")
                elif provider == "local":
                    base = api_url.strip().rstrip('/') if api_url else "http://localhost:3001"
                    send_url = f"{base}/instance/{whatsapp_instance_id}/send"
                    payload = {
                        "to": data.sender_id,
                        "message": data.message
                    }
                    try:
                        res = requests.post(send_url, json=payload, timeout=10)
                        if res.status_code == 200 and res.json().get("status") == "success":
                            send_success = True
                        else:
                            api_error = res.text
                            print(f"❌ Local WA send failed in chat.py: {res.text}")
                    except Exception as e:
                        api_error = str(e)
                        print(f"❌ Local WA exception in chat.py: {e}")
            else:
                print(f"⚠️ Could not fetch credentials for whatsapp_instance_id {whatsapp_instance_id}, falling back to Meta API")

        # Fallback to Meta API
        if not routed_via_custom or not send_success:
            if not whatsapp_instance_id:
                url = f"https://graph.facebook.com/v17.0/{PHONE_ID}/messages"
                headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
                payload = { "messaging_product": "whatsapp", "to": data.sender_id, "type": "text", "text": {"body": data.message} }
                try:
                    r = requests.post(url, headers=headers, json=payload)
                    if r.status_code not in [200, 201]:
                        api_error = r.text
                        print(f"❌ Meta WA send failed in chat.py: {r.text}")
                    else:
                        send_success = True
                except Exception as e:
                    api_error = str(e)
                    print(f"❌ Meta WA Send Exception in chat.py: {e}")
            else:
                if not api_error:
                    api_error = "Custom WhatsApp instance send failed"

    elif channel == 'messenger':
        if not FB_PAGE_TOKEN:
            api_error = "FB_PAGE_TOKEN is empty"
            print("⚠️ FB_PAGE_TOKEN is empty. Message will be saved but not sent to Facebook.")
        else:
            url = f"https://graph.facebook.com/v18.0/me/messages?access_token={FB_PAGE_TOKEN}"
            headers = {"Content-Type": "application/json"}
            payload = { "recipient": {"id": data.sender_id}, "message": {"text": data.message} }
            try:
                r = requests.post(url, headers=headers, json=payload)
                if r.status_code != 200:
                    api_error = r.text
                    print(f"❌ Failed to send Messenger: {r.text}")
                else:
                    send_success = True
            except Exception as e:
                api_error = str(e)
                print(f"❌ Messenger Send Exception: {e}")

    elif channel == 'instagram':
        if not INSTAGRAM_TOKEN:
            api_error = "INSTAGRAM_TOKEN is empty"
            print("⚠️ INSTAGRAM_TOKEN is empty for Instagram.")
        else:
            # Step 1: Try to take thread control (Handover Protocol)
            try:
                take_url = f"https://graph.facebook.com/v18.0/me/take_thread_control"
                take_payload = {"recipient": {"id": data.sender_id}}
                tc_res = requests.post(take_url, headers={"Content-Type": "application/json"},
                                      params={"access_token": FB_PAGE_TOKEN}, json=take_payload, timeout=5)
                if tc_res.status_code == 200:
                    print(f"[IG-Handover] Successfully took thread control for {data.sender_id}")
                else:
                    print(f"[IG-Handover] take_thread_control: {tc_res.status_code} {tc_res.text}")
            except Exception as tc_err:
                print(f"[IG-Handover] Exception: {tc_err}")

            # Step 2: Send the message
            url = f"https://graph.instagram.com/v18.0/me/messages?access_token={INSTAGRAM_TOKEN}"
            headers = {"Content-Type": "application/json"}
            payload = { "recipient": {"id": data.sender_id}, "message": {"text": data.message} }
            try:
                r = requests.post(url, headers=headers, json=payload)
                if r.status_code == 200:
                    send_success = True
                else:
                    err_json = {}
                    try: err_json = r.json()
                    except: pass
                    err_code = err_json.get('error', {}).get('error_subcode', 0)
                    if err_code == 2534037:
                        api_error = "instagram_handover_error"
                        print("[IG-HANDOVER] App has no thread control. Attempting send via FB Page token...")
                        # Retry with Facebook Page token
                        try:
                            fb_url = f"https://graph.facebook.com/v18.0/me/messages?access_token={FB_PAGE_TOKEN}"
                            fb_r = requests.post(fb_url, headers=headers, json=payload, timeout=10)
                            if fb_r.status_code == 200:
                                send_success = True
                                api_error = ""
                                print(f"[IG-HANDOVER] Retry via FB token succeeded for {data.sender_id}")
                            else:
                                print(f"[IG-HANDOVER] Retry via FB token also failed: {fb_r.status_code} {fb_r.text}")
                        except Exception as fb_err:
                            print(f"[IG-HANDOVER] FB token retry exception: {fb_err}")
                    elif err_code == 2534022:
                        api_error = "instagram_window_expired"
                        print(f"[IG-WINDOW] 24-hour messaging window expired for {data.sender_id}")
                    elif err_code == 2534048:
                        api_error = "instagram_dev_mode"
                        print("[IG-DEV-MODE] App in Dev Mode - recipient has no role on app.")
                    else:
                        api_error = r.text
                        print(f"❌ Failed to send Instagram: {r.text}")
            except Exception as e:
                api_error = str(e)
                print(f"❌ Instagram Send Exception: {e}")
    else:
        raise HTTPException(status_code=400, detail="Invalid channel type")

    # 2. حفظ الرسالة في Supabase (كـ رسالة من الموظف)
    supabase_url = f"{SUPABASE_URL}/rest/v1/omnichannel_messages"
    db_payload = {
        "channel": channel,
        "sender_id": data.sender_id,
        "sender_name": "Admin",
        "message_text": data.message,
        "is_from_admin": True,
        "read_by_admin": True
    }
    if channel == "whatsapp" and whatsapp_instance_id:
        db_payload["whatsapp_instance_id"] = whatsapp_instance_id
    
    try:
        response = requests.post(supabase_url, headers=SUPABASE_HEADERS, json=db_payload)
        if response.status_code not in [200, 201]:
             print(f"❌ Supabase save error: {response.text}")
             raise HTTPException(status_code=500, detail="Message sent but failed to save in Database")
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

    if api_error == "instagram_handover_error":
        return {
            "status": "warning",
            "message": "تم حفظ الرسالة، لكن لم تُرسل للعميل. يرجى الذهاب لإعدادات صفحة فيسبوك -> Advanced Messaging وتعيين تطبيقك كـ Primary Receiver للإنستجرام."
        }
    elif api_error == "instagram_window_expired":
        return {
            "status": "warning",
            "message": "⚠️ انتهت مهلة الـ 24 ساعة! لا يمكن الرد على هذا العميل لأنه لم يرسل رسالة خلال آخر 24 ساعة. يرجى الرد عليه من تطبيق Instagram مباشرة أو انتظار رسالة جديدة منه."
        }
    elif api_error == "instagram_dev_mode":
        return {
            "status": "warning",
            "message": "تم حفظ الرسالة، لكن لم يتم إرسالها على إنستجرام. التطبيق في وضع التطوير ويحتاج Advanced Access من Meta. الرسالة ظهرت في المحادثة فقط."
        }
    elif api_error:
        raise HTTPException(status_code=502, detail=f"API Error: {api_error}")

    return {"status": "success", "message": f"Reply sent successfully via {channel}"}