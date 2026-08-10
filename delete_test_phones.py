"""
حذف السجلات التجريبية مع معالجة Foreign Keys
الأرقام: 01114323218, 01121748885
"""
import requests

SB_URL = 'https://khskudtxbypohvnreloi.supabase.co'
SB_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imtoc2t1ZHR4Ynlwb2h2bnJlbG9pIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODYzMTIwMjksImV4cCI6MjEwMTg4ODAyOX0.jrK8y5zpDncgFkmdD4hkFRd5-kW1gWdVSRIb0jh7o2I'
H = {'apikey': SB_KEY, 'Authorization': f'Bearer {SB_KEY}', 'Content-Type': 'application/json'}

# السجلات المتبقية التي فشل حذفها (من نتيجة السكريبت السابق)
BLOCKED_PROFILE_IDS = [
    '0774c39a-5d53-4e6d-905a-8b0e370b3353',  # احمد علام تست 4
    'e53c9764-d89f-4068-a367-91e20731f717',  # احمد هاشم علام
    '2718a747-86e5-4820-93a0-b1e107ca57be',  # noha
    'ecc1499f-07b2-46ab-8fac-aadfd24fb615',  # احمد
]

BLOCKED_DRIVER_IDS = [1, 31]  # نوح, تست سواق - مرتبطان بـ trips

def delete(table, field, value):
    r = requests.delete(f'{SB_URL}/rest/v1/{table}?{field}=eq.{value}', headers=H)
    ok = r.status_code in [200, 204]
    if not ok:
        print(f"    ❌ فشل {table}/{field}={value}: {r.status_code} {r.text[:120]}")
    return ok

print("=" * 60)
print("🗑️  حذف السجلات المحجوبة بـ Foreign Key")
print("=" * 60)

# ===============================================
# 1. معالجة الـ profiles المرتبطة بـ support_chats
# ===============================================
print("\n📌 خطوة 1: حذف support_chats المرتبطة بالـ profiles")
for pid in BLOCKED_PROFILE_IDS:
    r = requests.delete(f'{SB_URL}/rest/v1/support_chats?user_id=eq.{pid}', headers=H)
    if r.status_code in [200, 204]:
        print(f"  ✅ حُذفت support_chats للـ profile: {pid[:20]}...")
    else:
        # قد يكون مرتبطاً بجداول فرعية أخرى
        print(f"  ⚠️  support_chats للـ profile: {pid[:20]}... → {r.status_code} {r.text[:100]}")

print("\n📌 خطوة 2: حذف trips المرتبطة بالـ profiles")
for pid in BLOCKED_PROFILE_IDS:
    # تحديث trips لإزالة الـ user_id (بدل الحذف عشان نحافظ على بيانات الرحلات)
    r = requests.patch(
        f'{SB_URL}/rest/v1/trips?user_id=eq.{pid}',
        headers=H,
        json={'user_id': None}
    )
    if r.status_code in [200, 204]:
        print(f"  ✅ تم إزالة user_id من trips للـ profile: {pid[:20]}...")

print("\n📌 خطوة 3: حذف الـ profiles المتبقية")
for pid in BLOCKED_PROFILE_IDS:
    # جرب حذف أي ارتباطات أخرى محتملة
    for tbl in ['loyalty_rewards', 'transactions', 'coupons']:
        requests.delete(f'{SB_URL}/rest/v1/{tbl}?user_id=eq.{pid}', headers=H)
    
    r = requests.delete(f'{SB_URL}/rest/v1/profiles?id=eq.{pid}', headers=H)
    if r.status_code in [200, 204]:
        print(f"  ✅ حُذف profile: {pid[:20]}...")
    else:
        print(f"  ❌ فشل profile {pid[:20]}...: {r.status_code} {r.text[:200]}")

# ===============================================
# 2. معالجة الـ drivers المرتبطة بـ trips
# ===============================================
print("\n📌 خطوة 4: معالجة السواقين المرتبطين بـ trips")
for did in BLOCKED_DRIVER_IDS:
    # فحص عدد الرحلات
    r = requests.get(f'{SB_URL}/rest/v1/trips?driver_id=eq.{did}&select=id&limit=5', headers=H)
    trips = r.json() if r.status_code == 200 else []
    print(f"  Driver #{did}: {len(trips)} رحلة مرتبطة")
    
    if len(trips) > 0:
        print(f"    ⚠️  لا يمكن حذف الكابتن #{did} لأنه مرتبط برحلات حقيقية")
        print(f"    💡 بدلاً من ذلك، سنغيّر رقمه لتجنب التعارض")
        # غيّر الرقم عشان ما يعارضش
        old_r = requests.get(f'{SB_URL}/rest/v1/drivers?id=eq.{did}&select=phone,name', headers=H)
        if old_r.status_code == 200 and old_r.json():
            old_data = old_r.json()[0]
            new_phone = f"TEST_DELETED_{did}"
            r2 = requests.patch(
                f'{SB_URL}/rest/v1/drivers?id=eq.{did}',
                headers=H,
                json={'phone': new_phone}
            )
            if r2.status_code in [200, 204]:
                print(f"    ✅ تم تغيير رقم الكابتن '{old_data['name']}' من {old_data['phone']} إلى {new_phone}")
            else:
                print(f"    ❌ فشل تغيير الرقم: {r2.text[:100]}")
    else:
        r = requests.delete(f'{SB_URL}/rest/v1/drivers?id=eq.{did}', headers=H)
        if r.status_code in [200, 204]:
            print(f"  ✅ حُذف driver #{did}")

# ===============================================
# 3. تحديث رقم driver #1 "نوح" إذا كان الرقم التجريبي
# ===============================================
print("\n📌 خطوة 5: التحقق من driver #1 (نوح)")
r = requests.get(f'{SB_URL}/rest/v1/drivers?id=eq.1&select=id,name,phone', headers=H)
if r.status_code == 200 and r.json():
    d = r.json()[0]
    print(f"  Driver #1: '{d['name']}' - phone: {d['phone']}")
    if d['phone'] and ('1114323218' in d['phone']):
        r2 = requests.patch(f'{SB_URL}/rest/v1/drivers?id=eq.1', headers=H, json={'phone': 'TEST_DELETED_1'})
        if r2.status_code in [200, 204]:
            print(f"  ✅ تم تغيير رقم 'نوح' لتجنب التعارض")

print("\n" + "=" * 60)
print("✅ اكتمل!")
print("=" * 60)
print()
print("📋 ما تبقى (يحتاج حذف يدوي من Supabase Auth Dashboard):")
print("  - المستخدمون في Supabase Auth بنفس الأرقام")
print("  - انتقل لـ: https://supabase.com → Authentication → Users")
print("  - ابحث عن ahmadhashemalam9@gmail.com")
print("  - ابحث عن 01114323218@24seven-client.app")
