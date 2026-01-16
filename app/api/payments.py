from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app import models
from app.api.auth import get_current_user
from pydantic import BaseModel  # <-- ضروري لنظام الكوبونات
import shutil
import os
import uuid

router = APIRouter()

# تأكد من وجود مجلد للصور
UPLOAD_DIR = "static/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ---------------------------------------------------------
# 1. نظام رفع إيصالات الدفع (تحويل بنكي / فودافون كاش)
# ---------------------------------------------------------

@router.post("/submit-request")
async def submit_payment(
    amount: int = Form(...),
    file: UploadFile = File(...),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    يستقبل صورة التحويل والمبلغ من العميل
    """
    # 1. حفظ الصورة باسم فريد
    file_extension = file.filename.split(".")[-1]
    unique_filename = f"{uuid.uuid4()}.{file_extension}"
    file_path = os.path.join(UPLOAD_DIR, unique_filename)
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    # 2. تسجيل الطلب في قاعدة البيانات
    # سنفترض مؤقتاً أن 1 جنيه = 1 توكن (يمكنك تغيير المعادلة)
    tokens = amount 
    
    new_payment = models.PaymentRequest(
        user_id=current_user.id,
        amount=amount,
        tokens_requested=tokens,
        proof_image=unique_filename, # نحفظ الاسم فقط
        status="Pending"
    )
    
    db.add(new_payment)
    db.commit()
    
    return {"message": "Payment submitted successfully", "id": new_payment.id}

# ---------------------------------------------------------
# 2. نظام تفعيل الكوبونات (Gift Cards) - ✅ الجديد
# ---------------------------------------------------------

class CouponRedeem(BaseModel):
    code: str

@router.post("/redeem-coupon")
def redeem_coupon(data: CouponRedeem, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """
    يقوم العميل بإدخال الكود، والسيستم يتحقق ويضيف الرصيد فوراً
    """
    # 1. البحث عن الكوبون وهل هو ساري؟
    coupon = db.query(models.Coupon).filter(models.Coupon.code == data.code, models.Coupon.is_active == True).first()
    
    if not coupon:
        raise HTTPException(status_code=400, detail="الكود غير صحيح أو تم استخدامه مسبقاً")
    
    # 2. إضافة قيمة الكوبون لرصيد المستخدم
    current_user.credits += coupon.value
    
    # 3. إبطال مفعول الكوبون (حتى لا يستخدمه شخص آخر)
    coupon.is_active = False 
    
    db.commit()
    
    return {
        "status": "success", 
        "message": f"مبروك! تم شحن {coupon.value} توكن بنجاح.", 
        "new_balance": current_user.credits,
        "added_value": coupon.value
    }