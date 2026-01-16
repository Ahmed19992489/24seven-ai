from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db
from app import models
from pydantic import BaseModel
from typing import List, Optional
import uuid  # <-- تم إضافة مكتبة التوليد العشوائي

router = APIRouter()

# --- النماذج (Pydantic) ---
class PaymentAction(BaseModel):
    request_id: int
    action: str

class CreditUpdate(BaseModel):
    user_id: int
    amount: int

class ExpenseCreate(BaseModel):
    label: str
    amount: float

# ✅ نموذج إنشاء الكوبون الجديد
class CouponCreate(BaseModel):
    value: int
    custom_code: Optional[str] = None

# --- نقطة الاتصال المحورية (Stats) ---
@router.get("/stats")
def get_admin_stats(db: Session = Depends(get_db)):
    """
    تحليل الأداء المالي الآمن (Crash-Proof):
    يعالج حالات الجداول الفارغة لمنع الأخطاء الحسابية.
    """
    # 1. العدادات البسيطة
    total_users = db.query(models.User).count()
    total_leads = db.query(models.Lead).count()
    
    # 2. حساب الإيرادات (استخدام 'or 0' للحماية من القيم الفارغة)
    total_revenue = db.query(func.sum(models.PaymentRequest.amount))\
        .filter(models.PaymentRequest.status == "Approved").scalar() or 0
    
    # 3. حساب المصروفات (استخدام 'or 0' للحماية)
    total_expenses = db.query(func.sum(models.Expense.amount)).scalar() or 0
    
    # 4. صافي الربح (الآن الطرح آمن لأن الطرفين أرقام)
    net_profit = total_revenue - total_expenses
    
    # 5. التارجت
    target_amount = 5000 
    progress_pct = int((total_revenue / target_amount) * 100) if total_revenue > 0 else 0

    # 6. ذكاء السوق
    top_keywords = db.query(models.SearchHistory.keyword, func.count(models.SearchHistory.keyword).label('count'))\
        .group_by(models.SearchHistory.keyword).order_by(func.count(models.SearchHistory.keyword).desc()).limit(5).all()
    
    top_locations = db.query(models.SearchHistory.location, func.count(models.SearchHistory.location).label('count'))\
        .group_by(models.SearchHistory.location).order_by(func.count(models.SearchHistory.location).desc()).limit(5).all()
    
    return {
        "total_users": total_users,
        "total_leads_captured": total_leads,
        "revenue_estimated": total_revenue, # يرسل كرقم خام (Frontend ينسقه)
        "net_profit": net_profit,           # يرسل كرقم خام
        
        # ✅ إرسال رقم المصروفات للواجهة ليتم عرضه
        "total_expenses_display": f"{total_expenses:,} EGP", 

        "progress_pct": min(100, progress_pct),
        "target_display": f"{target_amount:,} EGP",
        "top_keywords": [{"name": k.keyword, "count": k.count} for k in top_keywords],
        "top_locations": [{"name": l.location, "count": l.count} for l in top_locations]
    }

# --- إضافة مصروف ---
@router.post("/add-expense")
def add_expense(data: ExpenseCreate, db: Session = Depends(get_db)):
    # حفظ المصروف في قاعدة البيانات
    new_expense = models.Expense(label=data.label, amount=data.amount)
    db.add(new_expense)
    db.commit()
    return {"status": "success", "message": "Expense Added"}

# --- باقي الدوال الأساسية ---
@router.get("/users")
def get_all_users(db: Session = Depends(get_db)):
    users = db.query(models.User).all()
    return [{"id": u.id, "email": u.email, "full_name": getattr(u, 'full_name', 'جديد'), "company": u.company_name, "credits": u.credits} for u in users]

@router.get("/user-details/{user_id}")
def get_user_intelligence(user_id: int, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user: raise HTTPException(status_code=404)
    searches = db.query(models.SearchHistory).filter(models.SearchHistory.user_id == user_id).order_by(models.SearchHistory.search_date.desc()).all()
    financials = db.query(models.PaymentRequest).filter(models.PaymentRequest.user_id == user_id).order_by(models.PaymentRequest.created_at.desc()).all()
    return {
        "full_name": user.full_name, "email": user.email, "job_title": getattr(user, 'job_title', '-'), "phone": getattr(user, 'phone', '-'), "company_name": user.company_name, "address": getattr(user, 'address', '-'),
        "searches": [{"keyword": s.keyword, "location": s.location, "date": s.search_date.strftime("%Y-%m-%d")} for s in searches],
        "financials": [{"amount": f.amount, "status": f.status, "date": f.created_at.strftime("%Y-%m-%d")} for f in financials]
    }

@router.get("/pending-payments")
def get_pending_payments(db: Session = Depends(get_db)):
    payments = db.query(models.PaymentRequest).filter(models.PaymentRequest.status == "Pending").all()
    result = []
    for p in payments:
        user = db.query(models.User).filter(models.User.id == p.user_id).first()
        result.append({"id": p.id, "user_email": user.email if user else "Unknown", "amount": p.amount, "proof_image": p.proof_image})
    return result

@router.post("/process-payment")
def process_payment(data: PaymentAction, db: Session = Depends(get_db)):
    payment = db.query(models.PaymentRequest).filter(models.PaymentRequest.id == data.request_id).first()
    if not payment: raise HTTPException(status_code=404)
    if data.action == "approve":
        payment.status = "Approved"
        user = db.query(models.User).filter(models.User.id == payment.user_id).first()
        if user: user.credits += payment.tokens_requested
    elif data.action == "reject": payment.status = "Rejected"
    db.commit()
    return {"status": "success"}

# ---------------------------------------------------------
# ✅ الدوال الجديدة لنظام الكوبونات (Gift Cards)
# ---------------------------------------------------------

@router.post("/generate-coupon")
def generate_coupon(data: CouponCreate, db: Session = Depends(get_db)):
    """
    توليد كوبون جديد بقيمة محددة
    """
    # إذا لم يكتب المدير كود خاص، نولد كود عشوائي
    final_code = data.custom_code if data.custom_code else f"GIFT-{str(uuid.uuid4())[:8].upper()}"
    
    # التأكد من عدم تكرار الكود
    exists = db.query(models.Coupon).filter(models.Coupon.code == final_code).first()
    if exists:
        raise HTTPException(status_code=400, detail="هذا الكود موجود بالفعل")
    
    new_coupon = models.Coupon(
        code=final_code,
        value=data.value,
        is_active=True
    )
    db.add(new_coupon)
    db.commit()
    return {"status": "success", "code": final_code, "value": data.value}

@router.get("/active-coupons")
def get_active_coupons(db: Session = Depends(get_db)):
    """جلب الكوبونات السارية فقط لعرضها للمدير"""
    coupons = db.query(models.Coupon).filter(models.Coupon.is_active == True).order_by(models.Coupon.created_at.desc()).all()
    return [{"code": c.code, "value": c.value, "created_at": c.created_at.strftime("%Y-%m-%d")} for c in coupons]

@router.delete("/delete-coupon/{code}")
def delete_coupon(code: str, db: Session = Depends(get_db)):
    """حذف أو إيقاف كوبون"""
    coupon = db.query(models.Coupon).filter(models.Coupon.code == code).first()
    if coupon:
        db.delete(coupon)
        db.commit()
    return {"status": "deleted"}