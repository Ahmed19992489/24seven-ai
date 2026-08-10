from fastapi import APIRouter
from datetime import datetime, date, timedelta
import requests
import json

router = APIRouter()

# =====================================================
# 🔑 إعدادات واتساب
# =====================================================
WHATSAPP_TOKEN = "EAAPDbwUyvY0BQrm6ZB9qb62LU9hI50ZC9QOfZAO3VPA7ZCSnFSRMCb2kouBRkXu4LiVmRU2ydv1vLl00kKmgTFMN5ULJOpImor7i8oITjicjIjWiOLxTL7yltYrlF0RLxcdU6UNOaIdqo4Ouv0BnQ79OK2sgSLpHY9ZCQs4iRIxcpjnoxr8EWpV4FSgGTzgZDZD"
PHONE_ID = "597129733493778"

SUPABASE_URL = 'https://khskudtxbypohvnreloi.supabase.co'
SUPABASE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imtoc2t1ZHR4Ynlwb2h2bnJlbG9pIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODYzMTIwMjksImV4cCI6MjEwMTg4ODAyOX0.jrK8y5zpDncgFkmdD4hkFRd5-kW1gWdVSRIb0jh7o2I'
SUPABASE_HEADERS = {
    'apikey': SUPABASE_KEY,
    'Authorization': f'Bearer {SUPABASE_KEY}',
    'Content-Type': 'application/json'
}

# رقم واتساب الأدمن
ADMIN_WHATSAPP = "201121748885"

def send_whatsapp(phone: str, message: str):
    """إرسال رسالة واتساب"""
    url = f"https://graph.facebook.com/v17.0/{PHONE_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "text",
        "text": {"body": message}
    }
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=10)
        return r.status_code in [200, 201]
    except Exception as e:
        print(f"❌ WA Send Error: {e}")
        return False


def build_report(employee_name: str, bookings: list, messages: list, target_date: str) -> str:
    """بناء نص التقرير اليومي"""
    today_display = datetime.strptime(target_date, "%Y-%m-%d").strftime("%d/%m/%Y")
    
    total_bookings = len(bookings)
    total_revenue = sum(b.get('cost', 0) or 0 for b in bookings)
    
    # تحليل الحجوزات حسب النوع
    one_way = sum(1 for b in bookings if 'ذهاب' in (b.get('trip_type','')) and 'عودة' not in b.get('trip_type',''))
    round_trip = sum(1 for b in bookings if 'عودة' in (b.get('trip_type','')))
    
    # تحليل حالات العملاء
    new_clients = sum(1 for b in bookings if b.get('client_status') == 'جديد')
    old_clients = sum(1 for b in bookings if b.get('client_status') == 'قديم')
    
    # الرسائل المرسلة
    sent_msgs = len(messages)
    
    # تقييم أولي
    if total_bookings >= 5:
        rating = "⭐⭐⭐⭐⭐ ممتاز"
    elif total_bookings >= 3:
        rating = "⭐⭐⭐⭐ جيد جداً"
    elif total_bookings >= 1:
        rating = "⭐⭐⭐ جيد"
    else:
        rating = "⭐⭐ يحتاج تحسين"
    
    # نصائح التحسين
    tips = []
    if new_clients > 0:
        tips.append(f"✓ حجزت {new_clients} عميل جديد — استمر في المتابعة اليومية")
    if total_bookings == 0:
        tips.append("⚠️ لا توجد حجوزات اليوم — تأكد من متابعة الاستفسارات")
    if sent_msgs < 5:
        tips.append("⚠️ عدد الردود قليل — حاول الرد بسرعة أكبر على العملاء")
    if round_trip > 0:
        tips.append(f"✓ {round_trip} رحلة ذهاب وعودة — إيرادات أعلى")
    
    tips_text = "\n".join(tips) if tips else "✓ أداء منتظم، استمر!"
    
    report = f"""📊 *التقرير اليومي - {today_display}*
👤 الموظف: {employee_name}

📋 *ملخص الأداء:*
• إجمالي الحجوزات: {total_bookings}
• رحلات ذهاب: {one_way} | ذهاب وعودة: {round_trip}
• عملاء جدد: {new_clients} | عملاء قدامى: {old_clients}
• إجمالي الإيرادات: {int(total_revenue)} جنيه
• الرسائل المُرسلة: {sent_msgs}

🏆 *التقييم:* {rating}

💡 *ملاحظات وتحسينات:*
{tips_text}

شكراً على جهودك! 24Seven 🚀"""
    
    return report


@router.get("/generate")
async def generate_daily_report(target_date: str = None):
    """
    توليد وإرسال التقارير اليومية لجميع الموظفين.
    - يرسل لواتساب الموظف (إذا متاح) 
    - يرسل ملخصاً للأدمن على رقم 01121748885
    - يرجع البيانات للوحة الأدمن
    """
    if not target_date:
        target_date = date.today().strftime("%Y-%m-%d")
    
    # 1. جلب حجوزات اليوم مع اسم الموظف
    res = requests.get(
        f"{SUPABASE_URL}/rest/v1/google_reservations",
        headers=SUPABASE_HEADERS,
        params={
            "select": "booking_employee,cost,trip_type,client_status,created_at",
            "trip_date": f"eq.{target_date}"
        }
    )
    bookings = res.json() if res.status_code == 200 else []
    
    # 2. جلب الرسائل المرسلة من الموظفين اليوم
    today_start = f"{target_date}T00:00:00"
    today_end = f"{target_date}T23:59:59"
    msgs_res = requests.get(
        f"{SUPABASE_URL}/rest/v1/omnichannel_messages",
        headers=SUPABASE_HEADERS,
        params={
            "select": "sender_name,created_at",
            "is_from_admin": "eq.true",
            "created_at": f"gte.{today_start}",
            "order": "created_at.desc"
        }
    )
    all_messages = msgs_res.json() if msgs_res.status_code == 200 else []
    
    # 3. تجميع البيانات حسب الموظف
    employees = {}
    for b in bookings:
        emp = b.get('booking_employee') or 'غير محدد'
        if emp and emp not in ['', 'null']:
            if emp not in employees:
                employees[emp] = {'bookings': [], 'messages': []}
            employees[emp]['bookings'].append(b)
    
    for m in all_messages:
        emp = m.get('sender_name') or 'Admin'
        if emp not in ['Admin', 'ش'] and emp in employees:
            employees[emp]['messages'].append(m)
    
    # 4. بناء وإرسال التقارير
    reports = []
    admin_summary_parts = [f"📊 *ملخص أداء الفريق - {target_date}*\n"]
    
    for emp_name, data in employees.items():
        report_text = build_report(emp_name, data['bookings'], data['messages'], target_date)
        
        # إرسال للموظف على واتساب (إذا كان لديه رقم مسجل)
        emp_phone_res = requests.get(
            f"{SUPABASE_URL}/rest/v1/profiles",
            headers=SUPABASE_HEADERS,
            params={"select": "phone", "full_name": f"eq.{emp_name}"}
        )
        emp_phone_data = emp_phone_res.json() if emp_phone_res.status_code == 200 else []
        emp_phone_sent = False
        if emp_phone_data and emp_phone_data[0].get('phone'):
            phone = emp_phone_data[0]['phone'].replace('+', '').replace(' ', '').replace('-', '')
            if not phone.startswith('2'):
                phone = '2' + phone
            emp_phone_sent = send_whatsapp(phone, report_text)
        
        admin_summary_parts.append(
            f"👤 {emp_name}: {len(data['bookings'])} حجز | رسائل: {len(data['messages'])}"
        )
        
        reports.append({
            "employee": emp_name,
            "report": report_text,
            "bookings_count": len(data['bookings']),
            "messages_count": len(data['messages']),
            "sent_to_employee": emp_phone_sent
        })
    
    # 5. إرسال ملخص إجمالي للأدمن
    if not reports:
        admin_summary_parts.append("لا توجد بيانات حجوزات لهذا اليوم.")
    
    admin_summary = "\n".join(admin_summary_parts)
    admin_summary += f"\n\n📋 إجمالي: {sum(r['bookings_count'] for r in reports)} حجز من {len(reports)} موظف"
    
    admin_sent = send_whatsapp(ADMIN_WHATSAPP, admin_summary)
    
    return {
        "status": "success",
        "date": target_date,
        "reports": reports,
        "admin_summary": admin_summary,
        "admin_whatsapp_sent": admin_sent,
        "total_employees": len(reports)
    }
