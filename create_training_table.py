import requests
import os
import sys
sys.stdout.reconfigure(encoding='utf-8')

from dotenv import load_dotenv
load_dotenv()

SB_URL = "https://khskudtxbypohvnreloi.supabase.co"
SB_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imtoc2t1ZHR4Ynlwb2h2bnJlbG9pIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODYzMTIwMjksImV4cCI6MjEwMTg4ODAyOX0.jrK8y5zpDncgFkmdD4hkFRd5-kW1gWdVSRIb0jh7o2I"
SB_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imtoc2t1ZHR4Ynlwb2h2bnJlbG9pIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4NjMxMjAyOSwiZXhwIjoyMTAxODg4MDI5fQ.uyCTVGkoeoz4xB3r2muV_fLiI62QIw-65g2nVeIb62w")

USE_KEY = SB_SERVICE_KEY if SB_SERVICE_KEY else SB_ANON_KEY

HEADERS = {
    "apikey": USE_KEY,
    "Authorization": f"Bearer {USE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

print(f"Connecting to Supabase: {SB_URL}")

# Check if table staff_training_reports exists
test_payload = {
    "employee_name": "Test Check",
    "session_type": "roleplay",
    "score": 85,
    "chat_history": {},
    "evaluation_report": "Test report"
}

r = requests.post(f"{SB_URL}/rest/v1/staff_training_reports", headers=HEADERS, json=test_payload)
print(f"Check staff_training_reports table response: {r.status_code}")

if r.status_code in (200, 201):
    print("✅ TABLE EXISTS AND WORKS! Test record inserted.")
    # Delete the test record
    requests.delete(f"{SB_URL}/rest/v1/staff_training_reports?employee_name=eq.Test Check", headers={**HEADERS, "Prefer": ""})
    print("Test record deleted.")
elif r.status_code == 404:
    print("\n❌ TABLE DOES NOT EXIST!")
    print("\nيرجى نسخ الكود التالي وتشغيله في Supabase Dashboard > SQL Editor:")
    print("=" * 60)
    sql = """
-- إنشاء جدول تقارير تدريب الموظفين
CREATE TABLE IF NOT EXISTS public.staff_training_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_name TEXT NOT NULL,
    session_type TEXT NOT NULL, -- 'roleplay' | 'course' | 'exam'
    score INTEGER, -- الدرجة من 100
    chat_history JSONB, -- المحادثة الكاملة
    evaluation_report TEXT, -- تقرير التقييم المفصل
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- تفعيل RLS
ALTER TABLE public.staff_training_reports ENABLE ROW LEVEL SECURITY;

-- السماح لجميع العمليات (عبر مفتاح الخدمة والـ API المفتوح)
CREATE POLICY "allow_all_training_reports" ON public.staff_training_reports
    FOR ALL USING (true) WITH CHECK (true);
    """
    print(sql)
    print("=" * 60)
else:
    print(f"Unexpected response: {r.status_code} - {r.text}")
