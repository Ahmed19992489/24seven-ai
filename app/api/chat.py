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
INSTAGRAM_TOKEN = "IGAAMRP14aPG1BZAGJmSTBHdjY1UGp5VEFjLTYzdGZAKaHRLaWE1Y2FuczNaeUhRYnAyRjdWX25vbktxb0xkZAEIyaWRwU2RKd201bFNaT0RzQk5INXhSTnczYnJSYUJWY05IVTBHSlQzX0libWlfTDNmZAXhROG40bmg0c2dWM2N2QQZDZD"  # Updated 2026-06-12

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
    
    send_success = False
    api_error = ""

    # 1. إرسال الرسالة عبر القناة المناسبة
    if channel == 'whatsapp':
        url = f"https://graph.facebook.com/v17.0/{PHONE_ID}/messages"
        headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
        payload = { "messaging_product": "whatsapp", "to": data.sender_id, "type": "text", "text": {"body": data.message} }
        try:
            r = requests.post(url, headers=headers, json=payload)
            if r.status_code not in [200, 201]:
                api_error = r.text
                print(f"❌ Failed to send WhatsApp: {r.text}")
            else:
                send_success = True
        except Exception as e:
            api_error = str(e)
            print(f"❌ WA Send Exception: {e}")

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
        if not FB_PAGE_TOKEN:
            api_error = "FB_PAGE_TOKEN is empty"
            print("⚠️ FB_PAGE_TOKEN is empty for Instagram.")
        else:
            url = f"https://graph.facebook.com/v17.0/me/messages?access_token={FB_PAGE_TOKEN}"
            headers = {"Content-Type": "application/json"}
            payload = { "recipient": {"id": data.sender_id}, "message": {"text": data.message} }
            try:
                r = requests.post(url, headers=headers, json=payload)
                if r.status_code == 200:
                    send_success = True
                elif r.status_code == 403:
                    err_json = {}
                    try: err_json = r.json()
                    except: pass
                    err_code = err_json.get('error', {}).get('error_subcode', 0)
                    if err_code == 2534048:
                        api_error = "instagram_dev_mode"
                        print("[IG-DEV-MODE] App in Dev Mode - recipient has no role on app.")
                    else:
                        api_error = r.text
                        print(f"❌ Failed to send Instagram: {r.text}")
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
    
    try:
        response = requests.post(supabase_url, headers=SUPABASE_HEADERS, json=db_payload)
        if response.status_code not in [200, 201]:
             print(f"❌ Supabase save error: {response.text}")
             raise HTTPException(status_code=500, detail="Message sent but failed to save in Database")
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

    if api_error == "instagram_dev_mode":
        return {
            "status": "warning",
            "message": "تم حفظ الرسالة، لكن لم يتم إرسالها على إنستجرام. التطبيق في وضع التطوير ويحتاج Advanced Access من Meta. الرسالة ظهرت في المحادثة فقط."
        }
    elif api_error:
        raise HTTPException(status_code=502, detail=f"API Error: {api_error}")

    return {"status": "success", "message": f"Reply sent successfully via {channel}"}