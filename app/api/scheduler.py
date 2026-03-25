"""
نظام الإرسال التلقائي للتقارير اليومية
يعمل كل يوم الساعة 12:00 منتصف الليل (توقيت القاهرة UTC+2)
"""
import requests
import json
from datetime import date, datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

# =====================================================
# 🔑 إعدادات WhatsApp Business API
# =====================================================
WA_TOKEN = "EAAPDbwUyvY0BQrm6ZB9qb62LU9hI50ZC9QOfZAO3VPA7ZCSnFSRMCb2kouBRkXu4LiVmRU2ydv1vLl00kKmgTFMN5ULJOpImor7i8oITjicjIjWiOLxTL7yltYrlF0RLxcdU6UNOaIdqo4Ouv0BnQ79OK2sgSLpHY9ZCQs4iRIxcpjnoxr8EWpV4FSgGTzgZDZD"
WA_PHONE_ID = "597129733493778"
WA_API_URL = f"https://graph.facebook.com/v17.0/{WA_PHONE_ID}/messages"
WA_HEADERS = {"Authorization": f"Bearer {WA_TOKEN}", "Content-Type": "application/json"}

# رقم الأدمن
ADMIN_PHONE = "201121748885"

# أسماء القوالب المعتمدة من Meta
TEMPLATE_TEAM    = "daily_team_report"
TEMPLATE_EMPLOYEE = "daily_employee_report"

# =====================================================
# إعدادات Supabase
# =====================================================
SUPABASE_URL = "https://wtjwzqvmwnbvjxnmweqq.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Ind0and6cXZtd25idmp4bm13ZXFxIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzE0NjU0MDMsImV4cCI6MjA4NzA0MTQwM30.kTFK22b18cc1BmvMyLTt-7V113jyf_YrodSB7Km00tY"
SB_HEADERS = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}

def insert_template_to_supabase(sender_id, template_name, params):
    """إدراج تقرير الواتساب في Supabase للظهور في المحادثات"""
    msg_text = f"[{template_name}]\n"
    if template_name == "daily_team_report":
        msg_text = f"📊 تقرير الفريق ({params[0]})\nحجوزات: {params[1]} | موظفين: {params[2]}\n{params[3]}"
    elif template_name == "daily_employee_report":
        msg_text = f"👤 تقرير الموظف ({params[0]})\n{params[1]} - حجوزات: {params[2]} | إيرادات: {params[3]} | عملاء جدد: {params[4]}\nالتقييم: {params[5]}"
    else:
        msg_text += " | ".join(params)

    url = f"{SUPABASE_URL}/rest/v1/omnichannel_messages"
    data = {
        "channel": "whatsapp",
        "sender_id": str(sender_id),
        "sender_name": "System",
        "message_text": msg_text,
        "is_from_admin": True
    }
    try:
        requests.post(url, headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json", "Prefer": "return=minimal"}, json=data, timeout=5)
    except Exception as e:
        print(f"Supabase Insert Error: {e}")


def send_template(phone: str, template_name: str, params: list) -> bool:
    """إرسال رسالة واتساب بالقالب المعتمد"""
    payload = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": "ar"},
            "components": [{
                "type": "body",
                "parameters": [{"type": "text", "text": str(p)} for p in params]
            }]
        }
    }
    try:
        r = requests.post(WA_API_URL, headers=WA_HEADERS, json=payload, timeout=10)
        result = r.json()
        if r.ok and result.get("messages"):
            print(f"✅ WA sent to {phone} via {template_name}")
            # [FIX] Save the sent report template to Supabase
            insert_template_to_supabase("+" + phone, template_name, params)
            return True
        else:
            print(f"❌ WA error to {phone}: {result.get('error', result)}")
            return int(False)
    except Exception as e:
        print(f"❌ WA exception: {e}")
        return False


def fetch_daily_data(target_date: str) -> dict:
    """جلب بيانات الحجوزات والموظفين من Supabase"""
    # حجوزات اليوم
    res = requests.get(
        f"{SUPABASE_URL}/rest/v1/google_reservations",
        headers=SB_HEADERS,
        params={"select": "booking_employee,cost,client_status,trip_type", "trip_date": f"eq.{target_date}"}
    )
    bookings = res.json() if res.status_code == 200 and isinstance(res.json(), list) else []

    # الموظفون الحقيقيون (لديهم إيميل + رقم هاتف)
    staff_res = requests.get(
        f"{SUPABASE_URL}/rest/v1/profiles",
        headers=SB_HEADERS,
        params={"select": "full_name,phone", "role": "in.(admin,moderator)", "email": "not.is.null"}
    )
    staff = staff_res.json() if staff_res.status_code == 200 and isinstance(staff_res.json(), list) else []

    return {"bookings": bookings, "staff": staff}


def build_employee_stats(bookings: list) -> dict:
    """تجميع إحصائيات كل موظف"""
    stats = {}
    for b in bookings:
        emp = (b.get("booking_employee") or "").strip()
        if not emp:
            continue
        if emp not in stats:
            stats[emp] = {"bookings": 0, "revenue": 0, "new_clients": 0}
        stats[emp]["bookings"] += 1
        stats[emp]["revenue"] += (b.get("cost") or 0)
        if b.get("client_status") == "جديد":
            stats[emp]["new_clients"] += 1
    return stats


def get_rating(bookings_count: int) -> str:
    if bookings_count >= 5: return "ممتاز"
    if bookings_count >= 3: return "جيد جدا"
    if bookings_count >= 1: return "جيد"
    return "يحتاج تحسين"


def get_tips(bookings_count: int, new_clients: int) -> str:
    tips = []
    if bookings_count >= 5:
        tips.append("أداء ممتاز - استمر في هذا المعدل")
    if new_clients > 0:
        tips.append(f"حجزت {new_clients} عميل جديد - تابع معهم")
    if bookings_count == 0:
        tips.append("لا حجوزات اليوم - راجع الاستفسارات الواردة")
    if bookings_count < 3:
        tips.append("ركز على تحويل الاستفسارات لحجوزات مؤكدة")
    return " | ".join(tips) if tips else "استمر في العمل الجيد"


def normalize_phone(phone: str) -> str:
    """تحويل رقم هاتف مصري للصيغة الدولية"""
    p = phone.strip().replace(" ", "").replace("-", "").replace("+", "")
    if p.startswith("0"):
        p = "2" + p
    elif p.startswith("1"):
        p = "20" + p
    return p


def send_daily_reports():
    """الدالة الرئيسية - تُستدعى كل يوم الساعة 12 ليلاً"""
    target_date = date.today().strftime("%Y-%m-%d")
    date_display = datetime.now(pytz.timezone("Africa/Cairo")).strftime("%-d %B %Y")

    print(f"\n📊 بدء إرسال التقارير اليومية - {target_date}")

    data = fetch_daily_data(target_date)
    bookings = data["bookings"]
    staff = data["staff"]

    emp_stats = build_employee_stats(bookings)
    total_bookings = sum(s["bookings"] for s in emp_stats.values())
    total_employees = len(emp_stats)

    # بناء ملخص الفريق ({{4}})
    team_lines = []
    for name, s in emp_stats.items():
        team_lines.append(f"{name}: {s['bookings']} حجز - {get_rating(s['bookings'])}")
    team_summary = " | ".join(team_lines) if team_lines else "لا توجد حجوزات"

    # 1️⃣ إرسال ملخص الفريق للأدمن
    admin_sent = send_template(
        ADMIN_PHONE,
        TEMPLATE_TEAM,
        [date_display, str(total_bookings), str(total_employees), team_summary]
    )
    print(f"📲 Admin report: {'✅' if admin_sent else '❌'}")

    # 2️⃣ إرسال تقرير شخصي لكل موظف عنده رقم هاتف
    staff_phone_map = {}
    for s in staff:
        if s.get("phone") and s.get("full_name"):
            staff_phone_map[s["full_name"].strip()] = normalize_phone(s["phone"])

    for emp_name, s in emp_stats.items():
        # محاولة مطابقة الاسم
        phone = staff_phone_map.get(emp_name)
        if not phone:
            # بحث جزئي
            for staff_name, staff_phone in staff_phone_map.items():
                if emp_name in staff_name or staff_name in emp_name:
                    phone = staff_phone
                    break

        if phone:
            tips = get_tips(s["bookings"], s["new_clients"])
            sent = send_template(
                phone,
                TEMPLATE_EMPLOYEE,
                [
                    date_display,
                    emp_name,
                    str(s["bookings"]),
                    str(int(s["revenue"])),
                    str(s["new_clients"]),
                    get_rating(s["bookings"]),
                    tips
                ]
            )
            print(f"📲 {emp_name} ({phone}): {'✅' if sent else '❌'}")
        else:
            print(f"⚠️ {emp_name}: لا يوجد رقم هاتف مسجل")

    print(f"✅ انتهى إرسال التقارير - {target_date}\n")


# =====================================================
# إعداد الـ Scheduler
# =====================================================
CAIRO_TZ = pytz.timezone("Africa/Cairo")
scheduler = BackgroundScheduler(timezone=CAIRO_TZ)


def start_scheduler():
    """تشغيل الـ scheduler - يُستدعى عند بدء السيرفر"""
    if not scheduler.running:
        # كل يوم الساعة 00:00 توقيت القاهرة
        scheduler.add_job(
            send_daily_reports,
            trigger=CronTrigger(hour=0, minute=0, timezone=CAIRO_TZ),
            id="daily_report",
            replace_existing=True
        )
        scheduler.start()
        print("⏰ Daily report scheduler started - runs at 00:00 Cairo time")


def stop_scheduler():
    """إيقاف الـ scheduler - يُستدعى عند إغلاق السيرفر"""
    if scheduler.running:
        scheduler.shutdown()
        print("⏰ Scheduler stopped")
