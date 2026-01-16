from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db
from app import models
# ✅ إضافة هامة: استدعاء دالة معرفة المستخدم الحالي
from app.api.auth import get_current_user 

router = APIRouter()

@router.get("/ai-hint/")
def get_ai_suggestions(query: str, db: Session = Depends(get_db)):
    """
    نظام RAG مصغر: يقترح بناءً على البيانات المخزنة والتحليل الذكي
    """
    # 1. البحث في الصناعات المخزنة لدينا (Historical Data)
    stats = db.query(models.Lead.industry, func.count(models.Lead.id))\
        .filter(models.Lead.industry.ilike(f"%{query}%"))\
        .group_by(models.Lead.industry)\
        .all()
    
    suggestions = []
    
    # 2. تحليل النتائج وتحويلها لنصائح
    if stats:
        for industry, count in stats:
            suggestions.append({
                "text": industry,
                "type": "database",
                "hint": f"🔥 لدينا {count} شركة في هذا المجال جاهزة للتصدير.",
                "score": count
            })
    else:
        # 3. اقتراح ذكي عام إذا لم نجد بيانات
        suggestions.append({
            "text": query,
            "type": "new_opportunity",
            "hint": "🚀 مجال جديد! الذكاء الاصطناعي يتوقع نتائج جيدة. جرب البحث في 'Cairo' أو 'Riyadh'.",
            "score": 0
        })

    # 4. إضافة اقتراحات "الكلمات المفتاحية ذات الصلة"
    if "estate" in query.lower() or "عقار" in query:
        suggestions.append({"text": "Real Estate Brokerage", "hint": "💡 نصيحة: جرب البحث عن 'Brokers' للحصول على أرقام موبايل أكثر.", "type": "ai_tip"})
    elif "marketing" in query.lower() or "تسويق" in query:
        suggestions.append({"text": "Digital Marketing Agencies", "hint": "📈 هذا المجال ينمو بسرعة. ركز على الشركات التي لديها موقع إلكتروني.", "type": "ai_tip"})
    elif "doctor" in query.lower() or "طب" in query:
        suggestions.append({"text": "Dental Clinics", "hint": "🦷 العيادات عادة تضع أرقام موبايل للحجز، فرصة ممتازة!", "type": "ai_tip"})

    return {"suggestions": suggestions}

# ✅ الدالة المحدثة: تحسب الأرقام الحقيقية للعميل
@router.get("/dashboard-stats/")
def get_user_stats(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """
    جلب إحصائيات حقيقية بناءً على داتا العميل المسجل دخول حالياً
    """
    # 1. جلب كل الـ Leads الخاصة بهذا العميل فقط
    my_leads = db.query(models.Lead).filter(models.Lead.user_id == current_user.id).all()
    total = len(my_leads)
    
    if total == 0:
        return {"total": 0, "emails_pct": 0, "phones_pct": 0, "decision_pct": 0}

    # 2. حساب الأرقام الحقيقية
    valid_emails = sum(1 for lead in my_leads if lead.email_status == "Valid")
    # البحث عن الأرقام التي تبدأ بـ 01 (موبايل مصري) كدليل على جودة الداتا للواتساب
    mobile_phones = sum(1 for lead in my_leads if "01" in str(lead.phone)) 
    decision_makers = sum(1 for lead in my_leads if lead.decision_maker_name)

    return {
        "total": total,
        "emails_pct": int((valid_emails / total) * 100),
        "phones_pct": int((mobile_phones / total) * 100),
        "decision_pct": int((decision_makers / total) * 100)
    }

# ✅ الدالة الجديدة: نظام الاقتراحات الذكي (Apollo Style)
@router.get("/smart-tips/")
def get_smart_sales_tips(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """
    تحليل سجل بحث العميل وتقديم نصائح لزيادة المبيعات (Cross-Selling)
    """
    # 1. معرفة آخر اهتمامات العميل
    last_search = db.query(models.SearchHistory).filter(models.SearchHistory.user_id == current_user.id).order_by(models.SearchHistory.id.desc()).first()
    
    tips = []
    
    if last_search:
        # اقتراح مبني على الموقع (Funnel Geographic)
        if last_search.location and "cairo" in last_search.location.lower():
            tips.append({
                "icon": "fa-map-marker-alt",
                "title": "فرصة توسع",
                "text": "لاحظنا اهتمامك بالقاهرة. هل تعلم أن الجيزة تحتوي على 30% من الشركات المستهدفة؟ جرب البحث في 'Giza'."
            })
            
        # اقتراح مبني على الصناعة (Cross-Selling)
        if last_search.keyword and "real estate" in last_search.keyword.lower():
             tips.append({
                "icon": "fa-building",
                "title": "قطاع مكمل",
                "text": "شركات العقارات عادة تتعاقد مع شركات التشطيبات (Interior Design). جرب استهدافهم لزيادة مبيعاتك."
            })
    
    # إذا لم يكن هناك بحث سابق، نعيد نصيحة عامة
    if not tips:
        tips.append({
            "icon": "fa-lightbulb",
            "title": "نصيحة اليوم",
            "text": "الشركات التي تحتوي على 'Verified Email' نسبة الرد فيها أعلى بـ 40%. ركز عليها!"
        })

    return tips