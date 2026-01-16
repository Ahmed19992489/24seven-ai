from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session
from app.database import get_db
from app import models
from app.api.auth import SECRET_KEY, ALGORITHM # استيراد مفاتيح التشفير مباشرة
from jose import jwt
import pandas as pd
import io # استخدام الذاكرة بدلاً من الملفات المؤقتة
from datetime import datetime

router = APIRouter()

@router.get("/download-leads/")
def download_leads(
    keyword: str, 
    location: str, 
    token: str = Query(None), 
    db: Session = Depends(get_db)
):
    # 1. التحقق من الهوية (Authentication) عبر التوكن الممرر في الرابط
    user = None
    if not token:
        raise HTTPException(status_code=401, detail="التوكن مفقود، يرجى تسجيل الدخول")
        
    try:
        # فك تشفير التوكن والتحقق من صلاحيته
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=401, detail="توكن غير صالح")
            
        user = db.query(models.User).filter(models.User.email == email).first()
    except Exception as e:
        print(f"❌ Auth Error during export: {e}")
        raise HTTPException(status_code=401, detail="جلسة العمل انتهت أو غير صالحة")
    
    if not user:
        raise HTTPException(status_code=401, detail="المستخدم غير موجود")

    # 2. جلب البيانات من قاعدة البيانات بناءً على الفلترة
    query = db.query(models.Lead).filter(models.Lead.user_id == user.id)

    if keyword and keyword != "All":
        query = query.filter(models.Lead.industry.ilike(f"%{keyword}%"))
    
    if location and location != "All":
        query = query.filter(models.Lead.location.ilike(f"%{location}%"))

    leads = query.order_by(models.Lead.id.desc()).all()

    # 3. تجهيز البيانات وتحويلها لتنسيق إكسيل
    data = []
    if not leads:
        data.append({"رسالة": "لا توجد بيانات متاحة لهذا البحث", "البحث": f"{keyword} في {location}"})
    else:
        for lead in leads:
            data.append({
                "Company Name": lead.company_name,
                "Industry": lead.industry,
                "Location": lead.location,
                "Verified Email": lead.email,
                "Email Status": lead.email_status,
                "Phone": lead.phone,
                "Decision Maker": lead.decision_maker_name,
                "Role": lead.decision_maker_role,
                "LinkedIn": lead.linkedin_url,
                "Website": lead.website,
                "Confidence": f"{lead.confidence_score}%"
            })

    # 4. الإنشاء في الذاكرة (Memory-based Writing) لتجاوز مشكلة مساحة الهارد
    try:
        output = io.BytesIO() # إنشاء وعاء في الرامات
        df = pd.DataFrame(data)
        
        # كتابة ملف الإكسيل داخل الوعاء في الرامات
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Leads')
        
        file_content = output.getvalue() # استخراج محتوى الملف كـ Bytes
        output.close()
            
    except Exception as e:
        print(f"❌ Excel Generation Error: {e}")
        raise HTTPException(status_code=500, detail="حدث خطأ أثناء إنشاء ملف الإكسيل")

    # 5. إعداد وإرسال الملف كاستجابة (Response)
    safe_filename = f"Leads_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    
    headers = {
        'Content-Disposition': f'attachment; filename="{safe_filename}"',
        'Content-Type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'Cache-Control': 'no-cache, no-store, must-revalidate',
        'Pragma': 'no-cache',
        'Expires': '0'
    }

    return Response(
        content=file_content, 
        headers=headers, 
        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )