from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from app.database import get_db
from app import models, schemas
from app.api.auth import get_current_user
from pydantic import BaseModel  # <-- 1. إضافة استيراد Pydantic

# استدعاء ملفات المحرك الحقيقي من المسار الصحيح (app.engines)
from app.engines.gmaps_collector import GmapsEngine
from app.engines.data_enricher import DataEnricher
from app.engines.verifier_pro import EmailVerifier

import time

router = APIRouter()

# --- دالة المحرك الشاملة (تنفذ في الخلفية) ---
def run_full_scraping_task(keyword: str, location: str, user_id: int, db: Session, limit: int):
    print(f"🚀 بدء محرك البحث الشامل لـ: {keyword} في {location}")
    
    gmaps = GmapsEngine()
    enricher = DataEnricher()
    verifier = EmailVerifier()
    
    try:
        # 1. سحب البيانات الأساسية من خرائط جوجل
        raw_results = gmaps.scrape(keyword, location, max_leads=limit)
        
        if not raw_results:
            print("⚠️ لم يتم العثور على نتائج في خرائط جوجل.")
            return

        # بدء جلسة البحث العميق عن الإيميلات وصناع القرار
        enricher.start_session()
        
        leads_saved = 0
        for item in raw_results:
            # 2. البحث العميق عن الإيميل وصانع القرار لكل شركة
            extra_data = enricher.find_emails_and_people(item['company_name'], item['website'])
            
            # 3. التحقق من صحة الإيميل تقنياً
            email_status, confidence = verifier.verify(extra_data['email'])
            
            # 4. حفظ البيانات الحقيقية في قاعدة البيانات
            new_lead = models.Lead(
                user_id=user_id,
                company_name=item['company_name'],
                industry=keyword,
                location=item['location'],
                phone=item['phone'],
                website=item['website'],
                email=extra_data['email'],
                email_status=email_status,
                confidence_score=confidence,
                decision_maker_name=extra_data['decision_maker_name'],
                decision_maker_role=extra_data['decision_maker_role'],
                linkedin_url=extra_data['linkedin_url']
            )
            db.add(new_lead)
            db.commit()
            leads_saved += 1
            print(f"✅ [SAVED] تم استخراج وحفظ: {item['company_name']}")

        enricher.stop_session()
        
        # 5. تسجيل العملية في سجل تاريخ البحث
        history = models.SearchHistory(
            user_id=user_id,
            keyword=keyword,
            location=location,
            results_count=leads_saved
        )
        db.add(history)
        db.commit()

    except Exception as e:
        print(f"❌ خطأ فني في المحرك الرئيسي: {e}")
        db.rollback()
    finally:
        # ضمان إغلاق جلسة المتصفح في كل الأحوال
        try:
            enricher.stop_session()
        except:
            pass

# --- 2. تعريف شكل البيانات المتوقعة (Schema) ---
class SearchRequest(BaseModel):
    keyword: str
    location: str
    target_limit: int = 5

# --- نقطة الاتصال لبدء البحث ---
@router.post("/start-search/")
def start_search(
    request: SearchRequest,  # <-- 3. استقبال البيانات كـ JSON Body
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    # 1. التأكد من وجود رصيد كافٍ (نستخدم request.target_limit)
    if current_user.credits < request.target_limit:
        raise HTTPException(status_code=400, detail="عذراً، رصيدك غير كافٍ لإتمام عملية البحث المطلوبة.")

    # 2. تفعيل خصم الرصيد فوراً من حساب المستخدم
    current_user.credits -= request.target_limit
    db.commit() # حفظ الخصم فوراً لضمان عدم التلاعب
    print(f"💰 تم خصم {request.target_limit} توكن من المستخدم {current_user.email}")

    # 3. إطلاق مهمة السحب والتحقق في الخلفية (نستخدم بيانات request)
    background_tasks.add_task(
        run_full_scraping_task, 
        request.keyword, 
        request.location, 
        current_user.id, 
        db, 
        request.target_limit
    )
    
    return {
        "status": "success", 
        "message": f"بدأ البحث بنجاح، تم خصم {request.target_limit} توكن من رصيدك. ستظهر النتائج تدريجياً في الجدول."
    }

# --- جلب بيانات المستخدم الحالية ---
@router.get("/my-leads/")
def get_my_leads(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    leads = db.query(models.Lead).filter(models.Lead.user_id == current_user.id).order_by(models.Lead.id.desc()).all()
    return {"data": leads}

# --- جلب سجل عمليات البحث ---
@router.get("/history")
def get_history(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    return db.query(models.SearchHistory).filter(models.SearchHistory.user_id == current_user.id).all()