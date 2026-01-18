from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from app.database import get_db
from app import models, schemas
from app.api.auth import get_current_user
from pydantic import BaseModel
import time

# استدعاء ملفات المحرك الحقيقي
# تأكد أن هذه الملفات موجودة في مجلد app/engines/
from app.engines.gmaps_collector import GmapsEngine
from app.engines.data_enricher import DataEnricher
from app.engines.verifier_pro import EmailVerifier

router = APIRouter()

# --- 1. تعريف شكل البيانات المتوقعة (Schema) ---
# هذا الكلاس هو "المترجم" الذي سيفهم البيانات القادمة من الداشبورد
class SearchRequest(BaseModel):
    keyword: str
    location: str
    target_limit: int = 5

# --- 2. دالة المحرك الشاملة (تنفذ في الخلفية) ---
def run_full_scraping_task(keyword: str, location: str, user_id: int, db: Session, limit: int):
    print(f"🚀 [Task Started] البحث عن: {keyword} في {location} (الحد الأقصى: {limit})")
    
    gmaps = GmapsEngine()
    enricher = DataEnricher()
    verifier = EmailVerifier()
    
    try:
        # أ) سحب البيانات الأساسية من خرائط جوجل
        # ملاحظة: تأكد أن الدالة gmaps.scrape تقبل المعاملات وتعمل بوضع Headless على السيرفر
        raw_results = gmaps.scrape(keyword, location, max_leads=limit)
        
        if not raw_results:
            print(f"⚠️ [Warning] لم يتم العثور على نتائج في خرائط جوجل لـ: {keyword}")
            return

        print(f"✅ تم العثور على {len(raw_results)} شركة. بدء الإثراء والتحقق...")

        # ب) بدء جلسة البحث العميق (الإثراء)
        enricher.start_session()
        
        leads_saved = 0
        for item in raw_results:
            # التحقق من وجود الشركة مسبقاً لتجنب التكرار (اختياري)
            # existing_lead = db.query(models.Lead).filter(models.Lead.company_name == item['company_name'], models.Lead.user_id == user_id).first()
            # if existing_lead: continue

            # ج) البحث العميق عن الإيميل وصانع القرار
            extra_data = enricher.find_emails_and_people(item['company_name'], item['website'])
            
            # د) التحقق من صحة الإيميل تقنياً
            email_status, confidence = verifier.verify(extra_data['email'])
            
            # هـ) حفظ البيانات في قاعدة البيانات
            new_lead = models.Lead(
                user_id=user_id,
                company_name=item['company_name'],
                industry=keyword,
                location=item['location'] or location, # استخدام الموقع المدخل كاحتياطي
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
            print(f"💾 [Saved] {item['company_name']} ({email_status})")

        enricher.stop_session()
        
        # و) تسجيل العملية في سجل التاريخ
        history = models.SearchHistory(
            user_id=user_id,
            keyword=keyword,
            location=location,
            results_count=leads_saved
        )
        db.add(history)
        db.commit()
        print(f"🏁 [Task Finished] تمت العملية بنجاح. تم حفظ {leads_saved} عميل.")

    except Exception as e:
        print(f"❌ [Critical Error] خطأ في المحرك الرئيسي: {e}")
        db.rollback()
    finally:
        try:
            enricher.stop_session()
        except:
            pass

# --- 3. نقطة الاتصال لبدء البحث (Endpoint) ---
@router.post("/start-search/")
def start_search(
    request: SearchRequest,  # استقبال البيانات كـ JSON Body
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    # أ) التحقق من الرصيد
    if current_user.credits < request.target_limit:
        raise HTTPException(status_code=400, detail="عذراً، رصيدك الحالي لا يكفي لهذه العملية.")

    # ب) خصم الرصيد فوراً
    current_user.credits -= request.target_limit
    db.commit()
    
    # ج) إرسال المهمة للخلفية (Background Task)
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
        "message": f"تم بدء البحث عن '{request.keyword}'. تم خصم {request.target_limit} نقطة. النتائج ستظهر تلقائياً عند اكتمالها."
    }

# --- 4. جلب النتائج (للعرض في الجدول) ---
@router.get("/my-leads/")
def get_my_leads(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    leads = db.query(models.Lead).filter(models.Lead.user_id == current_user.id).order_by(models.Lead.id.desc()).limit(100).all()
    return {"data": leads}

# --- 5. جلب سجل البحث (للقائمة الجانبية) ---
@router.get("/history")
def get_history(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    return db.query(models.SearchHistory).filter(models.SearchHistory.user_id == current_user.id).order_by(models.SearchHistory.id.desc()).all()