from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime
from app import models, database
from app.api.auth import get_current_user
from pydantic import BaseModel

router = APIRouter()

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