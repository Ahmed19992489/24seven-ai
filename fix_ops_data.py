"""
تصحيح قاعدة البيانات بناءً على حسابات مكتب التشغيل (المرجع الصحيح)
Fix system data based on operations manager's correct settlement sheet
"""

import os
from supabase import create_client

SUPABASE_URL = "https://khskudtxbypohvnreloi.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imtoc2t1ZHR4Ynlwb2h2bnJlbG9pIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODYzMTIwMjksImV4cCI6MjEwMTg4ODAyOX0.jrK8y5zpDncgFkmdD4hkFRd5-kW1gWdVSRIb0jh7o2I"

sb = create_client(SUPABASE_URL, SUPABASE_KEY)

# vendor_id للمكتب الخارجي (نفس الـ vendor_id الموجود في vendor_transactions الحالية)
VENDOR_ID = "344be688-a74a-4ed5-ae88-d7d0288c0a1b"

print("=" * 70)
print("🔧 تصحيح قاعدة البيانات - حسابات مكتب التشغيل (7-11 يونيو 2026)")
print("=" * 70)

errors = []
fixes_done = []

def fix_trip(trip_id, manager_price, manager_diff, manager_postpaid, trip_desc):
    """
    تصحيح رحلة واحدة بناءً على أرقام المكتب:
    - manager_price   = التحصيل (السعر الكلي)
    - manager_diff    = الفارق (عمولة 24SEVEN من الكاش)
    - manager_postpaid = الآجل (مبلغ مستحق 24SEVEN للمكتب)
    """
    print(f"\n{'─'*60}")
    print(f"🔧 تصحيح #{trip_id} | {trip_desc}")
    print(f"   المكتب → سعر={manager_price} | عمولة={manager_diff} | آجل={manager_postpaid}")

    # 1. تحديث estimated_price في trips
    up = sb.from_("trips").update({
        "estimated_price": manager_price,
        "final_price": manager_price,
    }).eq("id", trip_id).execute()
    print(f"   ✅ تحديث estimated_price و final_price = {manager_price}")

    # 2. حذف كل vendor_transactions القديمة لهذه الرحلة
    del_result = sb.from_("vendor_transactions").delete().eq("trip_id", trip_id).execute()
    deleted_count = len(del_result.data) if del_result.data else 0
    print(f"   🗑️  حذف {deleted_count} سجل vendor_transactions قديم")

    # 3. إضافة السجل الصحيح
    if manager_postpaid > 0:
        # رحلة آجل: المكتب يستحق مبلغ الآجل من 24SEVEN
        insert_data = {
            "vendor_id": VENDOR_ID,
            "trip_id": trip_id,
            "transaction_type": "deferred_credit",
            "amount": manager_postpaid,
            "description": f"[تصحيح] مستحق رحلة آجل #{trip_id} | {trip_desc} | آجل={manager_postpaid}"
        }
        res = sb.from_("vendor_transactions").insert([insert_data]).execute()
        print(f"   ✅ إضافة deferred_credit = {manager_postpaid} EGP")
        fixes_done.append(f"#{trip_id} ({trip_desc}): آجل = {manager_postpaid} EGP")

    if manager_diff > 0:
        # رحلة كاش: 24SEVEN تستقطع عمولة من المكتب
        insert_data = {
            "vendor_id": VENDOR_ID,
            "trip_id": trip_id,
            "transaction_type": "commission_deduction",
            "amount": -manager_diff,
            "description": f"[تصحيح] عمولة كاش #{trip_id} | {trip_desc} | عمولة={manager_diff}"
        }
        res = sb.from_("vendor_transactions").insert([insert_data]).execute()
        print(f"   ✅ إضافة commission_deduction = -{manager_diff} EGP")
        fixes_done.append(f"#{trip_id} ({trip_desc}): عمولة = {manager_diff} EGP")

    if manager_postpaid == 0 and manager_diff == 0:
        print(f"   ℹ️  لا عمولة ولا آجل - تم تحديث السعر فقط")

# =========================================================
# الورقة 1: 9-11 يونيو - التصحيحات المطلوبة
# =========================================================
print("\n📄 الورقة 1: 9-11 يونيو 2026")
print("=" * 70)

# الرحلات الصحيحة (يبقى vendor_transactions صح، بس نتأكد من السعر):
# #11308: price=2200, diff=500 ✅
fix_trip(11308, manager_price=2200, manager_diff=500, manager_postpaid=0, trip_desc="القاهرة → السخنة")

# #10979: price=1750, diff=250 ✅
fix_trip(10979, manager_price=1750, manager_diff=250, manager_postpaid=0, trip_desc="السخنة → القاهرة (سامية عاطف)")

# #11254: price=575, diff=0, آجل=500 ← النظام كان غلط (ضع عمولة 500 بدل آجل 500)
fix_trip(11254, manager_price=575, manager_diff=0, manager_postpaid=500, trip_desc="ذهاب مطار البرج")

# #11311: price=4300, diff=300 ✅
fix_trip(11311, manager_price=4300, manager_diff=300, manager_postpaid=0, trip_desc="القاهرة → العالمين (لؤى)")

# #11322: price=575, diff=75 ✅
fix_trip(11322, manager_price=575, manager_diff=75, manager_postpaid=0, trip_desc="القاهرة → البرج (طارق)")

# #11317: price=575, diff=75 ✅
fix_trip(11317, manager_price=575, manager_diff=75, manager_postpaid=0, trip_desc="ذهاب مطار البرج (وسام)")

# #11310: price=1450, diff=0, آجل=1300 ← النظام غلط (كان 4300 ومسجل كاش)
fix_trip(11310, manager_price=1450, manager_diff=0, manager_postpaid=1300, trip_desc="عودة مطار القاهرة (آجل)")

# #11325: price=4300, diff=300 ← النظام غلط (كان 2200 وعمولة 500)
fix_trip(11325, manager_price=4300, manager_diff=300, manager_postpaid=0, trip_desc="العالمين → مطار سفنكس (لؤى)")

# #131: price=2100, diff=600 ← النظام غلط (كان مسجل آجل 2800)
fix_trip(131, manager_price=2100, manager_diff=600, manager_postpaid=0, trip_desc="السخنة → القاهرة (الدعاء) كاش")

# #11212: price=3600, diff=0, آجل=2700 ← النظام غلط (كان 2200 وآجل=500)
fix_trip(11212, manager_price=3600, manager_diff=0, manager_postpaid=2700, trip_desc="مدينتي المراسي (هشام) آجل")

# =========================================================
# الورقة 2: 7-8 يونيو - التصحيحات المطلوبة
# =========================================================
print("\n📄 الورقة 2: 7-8 يونيو 2026")
print("=" * 70)

# #11295: price=575, diff=75 ← النظام غلط (كان 3550 وعمولة 450)
fix_trip(11295, manager_price=575, manager_diff=75, manager_postpaid=0, trip_desc="عودة مطار البرج (محمود)")

# #11222: price=3200, diff=400 ✅
fix_trip(11222, manager_price=3200, manager_diff=400, manager_postpaid=0, trip_desc="عودة مطار القاهرة (أحمد عاطف)")

# #11242: price=5800, diff=0, آجل=5400 ← النظام غلط (كان آجل=400)
fix_trip(11242, manager_price=5800, manager_diff=0, manager_postpaid=5400, trip_desc="رحلة آجل كبيرة")

# #11220: price=575, diff=75 ✅
fix_trip(11220, manager_price=575, manager_diff=75, manager_postpaid=0, trip_desc="ذهاب مطار البرج (راهد)")

# #11283: price=575, diff=75 ✅
fix_trip(11283, manager_price=575, manager_diff=75, manager_postpaid=0, trip_desc="ذهاب مطار القاهرة (رضوى)")

# #10919: price=2200, diff=500 ✅
fix_trip(10919, manager_price=2200, manager_diff=500, manager_postpaid=0, trip_desc="ذهاب مطار القاهرة (رمضان)")

# #11299: price=1450, diff=150 ✅
fix_trip(11299, manager_price=1450, manager_diff=150, manager_postpaid=0, trip_desc="عودة مطار القاهرة (معتز)")

# =========================================================
# الرحلات المفقودة من قاعدة البيانات (5 رحلات)
# =========================================================
print("\n" + "=" * 70)
print("⚠️  رحلات موجودة عند المكتب لكن غير موجودة في النظام")
print("=" * 70)

missing_trips = [
    {"code": 10978, "date": "7/6/2026", "desc": "القاهرة → السخنة (سامية عاطف)", "price": 1750, "diff": 350, "postpaid": 0},
    {"code": 11282, "date": "7/6/2026", "desc": "ذهاب التجمع (علا المطار)",        "price": 1200, "diff": 500, "postpaid": 0},
    {"code": 11230, "date": "7/6/2026", "desc": "الفرفرة → جسر السويس (إسلام)",   "price": 5700, "diff": 400, "postpaid": 0},
    {"code": 11291, "date": "7/6/2026", "desc": "ذهاب التجمع (شرين)",              "price": 1800, "diff": 500, "postpaid": 0},
    {"code": 11202, "date": "8/6/2026", "desc": "دار الفاهرة (شروق عثمان)",        "price": 4300, "diff": 0,   "postpaid": 3800},
]

print("\nهذه الرحلات لا يمكن إضافتها تلقائياً لأنها غير موجودة في جدول trips.")
print("يجب إضافتها يدوياً في النظام أو من خلال الشيت الخارجي.\n")

total_missing = 0
for t in missing_trips:
    net = t["diff"] + t["postpaid"]
    total_missing += (t["diff"] + t["postpaid"])
    type_label = "آجل" if t["postpaid"] > 0 else "كاش"
    print(f"  ❌ #{t['code']} | {t['date']} | {t['desc']}")
    print(f"     سعر={t['price']} | عمولة={t['diff']} | آجل={t['postpaid']} | نوع={type_label}")

print(f"\n  💰 إجمالي الرحلات المفقودة: {total_missing} EGP (عمولات + آجل)")

# =========================================================
# التحقق النهائي: حساب الأرقام بعد التصحيح
# =========================================================
print("\n" + "=" * 70)
print("📊 التحقق النهائي - حساب الأرقام بعد التصحيح")
print("=" * 70)

all_codes = [11308,10979,11254,11311,11322,11317,11310,11325,131,11212,
             11295,11222,11242,11220,11283,10919,11299]

vt_result = sb.from_("vendor_transactions").select("*").in_("trip_id", all_codes).execute()
vt_data = vt_result.data or []

total_deferred = sum(v["amount"] for v in vt_data if v.get("transaction_type") == "deferred_credit")
total_commission = sum(abs(v["amount"]) for v in vt_data if v.get("transaction_type") == "commission_deduction")
net = total_deferred - total_commission

print(f"\n  مجموع الآجل (deferred_credit):  {total_deferred} EGP")
print(f"  مجموع العمولات (commission):       {total_commission} EGP")
print(f"  صافي مستحق للمكتب:               {net} EGP")

# المطلوب حسب المكتب:
# ورقة 1: آجل=6200, فرق=2100 → صافي = 6200-2100 = 4100
# ورقة 2: آجل=9700, فرق=3700 → صافي = 9700-3700 = 6000
# إجمالي: آجل=15900, فرق=5800, صافي=10100
expected_deferred = 6200 + 9700
expected_commission = 2100 + 3700
expected_net = expected_deferred - expected_commission
print(f"\n  المتوقع (حسب المكتب):")
print(f"  مجموع الآجل:      {expected_deferred} EGP")
print(f"  مجموع العمولات:   {expected_commission} EGP")
print(f"  صافي مستحق:       {expected_net} EGP")

print(f"\n  الفرق المتبقي = {net} - {expected_net} = {net - expected_net} EGP")
if abs(net - expected_net) < 100:
    print("  ✅ الأرقام متطابقة!")
else:
    print("  ⚠️  لا تزال هناك فجوة - ربما بسبب الرحلات المفقودة الخمس")

print("\n" + "=" * 70)
print(f"✅ اكتمل التصحيح | تم تصحيح {len(fixes_done)} عملية")
print("=" * 70)
for f in fixes_done:
    print(f"  • {f}")
