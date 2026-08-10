"""
إنشاء جداول نظام المكالمات في Supabase عبر REST API
"""
import requests
import json

SB_URL = "https://khskudtxbypohvnreloi.supabase.co"
SB_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imtoc2t1ZHR4Ynlwb2h2bnJlbG9pIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODYzMTIwMjksImV4cCI6MjEwMTg4ODAyOX0.jrK8y5zpDncgFkmdD4hkFRd5-kW1gWdVSRIb0jh7o2I"

# نفس مفتاح service_role لو عندنا - لو لا سنستخدم anon
HEADERS = {
    "apikey": SB_KEY,
    "Authorization": f"Bearer {SB_KEY}",
    "Content-Type": "application/json"
}

# اختبار: هل يمكننا قراءة جدول trips
r = requests.get(f"{SB_URL}/rest/v1/trips?limit=1", headers=HEADERS)
print(f"Connection test: {r.status_code}")

# جرب إدراج سجل تجريبي في call_signals (سيفشل لو الجدول مش موجود)
test_data = {
    "call_id": "test-123",
    "from_user_id": "test-from",
    "to_user_id": "test-to", 
    "user_type": "driver",
    "signal_type": "offer",
    "payload": {}
}
r2 = requests.post(f"{SB_URL}/rest/v1/call_signals", headers=HEADERS, json=test_data)
print(f"call_signals test insert: {r2.status_code} - {r2.text[:200]}")

r3 = requests.post(f"{SB_URL}/rest/v1/push_subscriptions", headers=HEADERS, json={
    "user_id": "test", "user_type": "driver", "subscription": {}
})
print(f"push_subscriptions test insert: {r3.status_code} - {r3.text[:200]}")
