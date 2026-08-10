"""
إنشاء جدول call_logs في Supabase
هذا الجدول يحفظ سجل المكالمات لحل مشكلة المكالمات الفائتة
"""
import requests
import os

# اقرأ المتغيرات من .env
from dotenv import load_dotenv
load_dotenv()

SB_URL = os.getenv("SUPABASE_URL", "https://khskudtxbypohvnreloi.supabase.co")
SB_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
SB_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imtoc2t1ZHR4Ynlwb2h2bnJlbG9pIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODYzMTIwMjksImV4cCI6MjEwMTg4ODAyOX0.jrK8y5zpDncgFkmdD4hkFRd5-kW1gWdVSRIb0jh7o2I")

# استخدم service_role إن وُجد وإلا anon
USE_KEY = SB_SERVICE_KEY if SB_SERVICE_KEY else SB_ANON_KEY

HEADERS = {
    "apikey": USE_KEY,
    "Authorization": f"Bearer {USE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

print(f"Connecting to: {SB_URL}")
print(f"Using key type: {'service_role' if SB_SERVICE_KEY else 'anon'}")

# اختبار الاتصال
r = requests.get(f"{SB_URL}/rest/v1/trips?limit=1", headers=HEADERS)
print(f"Connection: {r.status_code}")

# محاولة إدراج سجل تجريبي في call_logs
# لو الجدول موجود سيعمل، لو لا سيفشل بـ 404
test_payload = {
    "call_id": "test_check_" + "12345",
    "caller_id": "test_caller",
    "caller_name": "Test",
    "caller_type": "moderator",
    "callee_id": "test_callee",
    "callee_name": "Test2",
    "callee_type": "driver",
    "status": "missed",
    "started_at": "2024-01-01T00:00:00Z"
}

r2 = requests.post(f"{SB_URL}/rest/v1/call_logs", headers=HEADERS, json=test_payload)
print(f"\ncall_logs table status: {r2.status_code}")

if r2.status_code in (200, 201):
    print("TABLE EXISTS AND WORKS - Test record inserted.")
    # احذف السجل التجريبي
    del_headers = {**HEADERS, "Prefer": ""}
    requests.delete(f"{SB_URL}/rest/v1/call_logs?call_id=eq.test_check_12345", headers=del_headers)
    print("Test record deleted.")
elif r2.status_code == 404:
    print("TABLE DOES NOT EXIST!")
    print("\nRun this SQL in Supabase Dashboard > SQL Editor:")
    print("=" * 60)
    sql = """
-- إنشاء جدول سجل المكالمات
CREATE TABLE IF NOT EXISTS public.call_logs (
    id BIGSERIAL PRIMARY KEY,
    call_id TEXT UNIQUE NOT NULL,
    caller_id TEXT NOT NULL,
    caller_name TEXT,
    caller_type TEXT,
    callee_id TEXT NOT NULL,
    callee_name TEXT,
    callee_type TEXT,
    status TEXT DEFAULT 'calling',
    started_at TIMESTAMPTZ DEFAULT NOW(),
    answered_at TIMESTAMPTZ,
    ended_at TIMESTAMPTZ,
    duration_seconds INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- فهرس للبحث السريع
CREATE INDEX IF NOT EXISTS idx_call_logs_callee ON public.call_logs(callee_id, status, started_at);
CREATE INDEX IF NOT EXISTS idx_call_logs_caller ON public.call_logs(caller_id, started_at);

-- تفعيل RLS
ALTER TABLE public.call_logs ENABLE ROW LEVEL SECURITY;

-- سياسة: الجميع يمكنهم القراءة والكتابة (يمكن تضييقها لاحقاً)
CREATE POLICY "allow_all_call_logs" ON public.call_logs
    FOR ALL USING (true) WITH CHECK (true);
    """
    print(sql)
    print("=" * 60)
else:
    print(f"Unexpected response: {r2.text[:300]}")
