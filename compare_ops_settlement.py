"""
مقارنة حسابات مكتب التشغيل مع قاعدة بياناتنا
Compare ops manager settlement vs our system data
"""

import os
from supabase import create_client

SUPABASE_URL = "https://wtjwzqvmwnbvjxnmweqq.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Ind0and6cXZtd25idmp4bm13ZXFxIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzE0NjU0MDMsImV4cCI6MjA4NzA0MTQwM30.kTFK22b18cc1BmvMyLTt-7V113jyf_YrodSB7Km00tY"

sb = create_client(SUPABASE_URL, SUPABASE_KEY)

# ===== بيانات المكتب من الصورتين =====
# الورقة 1: 9-11 يونيو 2026
sheet1 = [
    {"code": 11308, "date": "9/6/2026",  "dest": "القاهرة → السخنة",         "client": "جماعة",       "car": "مينى فان", "collected": 2200, "diff": 500,  "postpaid": 0},
    {"code": 10979, "date": "9/6/2026",  "dest": "السخنة → القاهرة",          "client": "سامية عاطف", "car": "سيدان",    "collected": 1750, "diff": 250,  "postpaid": 0},
    {"code": 11254, "date": "9/6/2026",  "dest": "ذهاب مطار البرج",           "client": "",           "car": "سيدان",    "collected": 575,  "diff": 0,    "postpaid": 500},
    {"code": 11311, "date": "9/6/2026",  "dest": "القاهرة → العالمين",        "client": "لؤى",        "car": "فان",      "collected": 4300, "diff": 300,  "postpaid": 0},
    {"code": 11322, "date": "10/6/2026", "dest": "القاهرة → البرج",           "client": "طارق",       "car": "سيدان",    "collected": 575,  "diff": 75,   "postpaid": 0},
    {"code": 11317, "date": "10/6/2026", "dest": "ذهاب مطار البرج",           "client": "وسام",       "car": "سيدان",    "collected": 575,  "diff": 75,   "postpaid": 0},
    {"code": 11310, "date": "11/6/2026", "dest": "عودة مطار القاهرة",         "client": "سنة",        "car": "سيدان",    "collected": 1450, "diff": 0,    "postpaid": 1300},
    {"code": 11325, "date": "11/6/2026", "dest": "العالمين → مطار سفنكس",     "client": "لؤى",        "car": "فان",      "collected": 4300, "diff": 300,  "postpaid": 0},
    {"code": 131,   "date": "11/6/2026", "dest": "السخنة → القاهرة",          "client": "الدعاء",     "car": "مينى فان", "collected": 2100, "diff": 600,  "postpaid": 0},
    {"code": 11212, "date": "11/6/2026", "dest": "من مدينتي المراسي",         "client": "هشام",       "car": "سيدان",    "collected": 3600, "diff": 0,    "postpaid": 2700},
    {"code": None,  "date": "11/6/2026", "dest": "ذهاب العاشر",               "client": "أحمد صلاح", "car": "سيدان",    "collected": 2200, "diff": 0,    "postpaid": 1700},
]

# الورقة 2: 7-8 يونيو 2026
sheet2 = [
    {"code": 10978, "date": "7/6/2026",  "dest": "القاهرة → السخنة",          "client": "سامية عاطف", "car": "سيدان",    "collected": 1750, "diff": 350,  "postpaid": 0},
    {"code": 11282, "date": "7/6/2026",  "dest": "ذهاب التجمع",               "client": "علا المطار", "car": "سيدان",    "collected": 1200, "diff": 500,  "postpaid": 0},
    {"code": 11230, "date": "7/6/2026",  "dest": "الفرفرة → جسر السويس",      "client": "إسلام الشامي","car": "فان",     "collected": 5700, "diff": 400,  "postpaid": 0},
    {"code": 11291, "date": "7/6/2026",  "dest": "ذهاب التجمع",               "client": "شرين",       "car": "سيدان",    "collected": 1800, "diff": 500,  "postpaid": 0},
    {"code": 11295, "date": "7/6/2026",  "dest": "عودة مطار البرج",           "client": "محمود",      "car": "سيدان",    "collected": 575,  "diff": 75,   "postpaid": 0},
    {"code": "خارجي","date": "7/6/2026", "dest": "ذهاب مطار القاهرة",         "client": "محمد",       "car": "سيدان",    "collected": 0,    "diff": 0,    "postpaid": 500},
    {"code": 11222, "date": "8/6/2026",  "dest": "عودة مطار القاهرة",         "client": "أحمد عاطف", "car": "فان",      "collected": 3200, "diff": 400,  "postpaid": 0},
    {"code": 11242, "date": "8/6/2026",  "dest": "(unclear)",                  "client": "",           "car": "",         "collected": 5800, "diff": 0,    "postpaid": 5400},
    {"code": 11202, "date": "8/6/2026",  "dest": "دار الفاهرة",               "client": "شروق عثمان","car": "مينى فان", "collected": 4300, "diff": 0,    "postpaid": 3800},
    {"code": 11220, "date": "8/6/2026",  "dest": "ذهاب مطار البرج",           "client": "راهد",       "car": "سيدان",    "collected": 575,  "diff": 75,   "postpaid": 0},
    {"code": 11283, "date": "8/6/2026",  "dest": "ذهاب مطار القاهرة",         "client": "رضوى",       "car": "سيدان",    "collected": 575,  "diff": 75,   "postpaid": 0},
    {"code": 10919, "date": "8/6/2026",  "dest": "ذهاب مطار القاهرة",         "client": "رمضان",      "car": "مينى فان", "collected": 2200, "diff": 500,  "postpaid": 0},
    {"code": 11299, "date": "8/6/2026",  "dest": "عودة مطار القاهرة",         "client": "معتز",       "car": "سيدان",    "collected": 1450, "diff": 150,  "postpaid": 0},
]

all_sheets = sheet1 + sheet2

# استخراج كودات رقمية فقط
numeric_codes = [r["code"] for r in all_sheets if isinstance(r["code"], int)]

print("=" * 80)
print("📊 مقارنة حسابات مكتب التشغيل مع قاعدة بياناتنا")
print("=" * 80)

# ===== جلب الرحلات من قاعدة البيانات =====
print(f"\n🔍 جلب {len(numeric_codes)} رحلة من قاعدة البيانات...")

result = sb.from_("trips").select(
    "id, status, estimated_price, final_price, admin_notes, "
    "created_at, manual_client_name, client_phone, pickup_location, dropoff_location, "
    "is_outsourced, our_commission, vendor_id"
).in_("id", numeric_codes).execute()

trips_db = {t["id"]: t for t in (result.data or [])}

# جلب vendor_transactions لهذه الرحلات
vt_result = sb.from_("vendor_transactions").select("*").in_("trip_id", numeric_codes).execute()
vt_by_trip = {}
for vt in (vt_result.data or []):
    tid = vt["trip_id"]
    if tid not in vt_by_trip:
        vt_by_trip[tid] = []
    vt_by_trip[tid].append(vt)

print(f"✅ تم جلب {len(trips_db)} رحلة من الداتابيز")

# ===== التحليل =====
print("\n" + "=" * 80)
print("📋 تفاصيل المقارنة")
print("=" * 80)

issues = []
not_found = []
postpaid_ok = []
postpaid_missing = []

for sheet_num, sheet in enumerate([sheet1, sheet2], 1):
    print(f"\n{'='*40}")
    print(f"📄 الورقة {sheet_num} ({'9-11 يونيو' if sheet_num==1 else '7-8 يونيو'})")
    print(f"{'='*40}")

    sheet_total_postpaid = sum(r["postpaid"] for r in sheet)
    sheet_total_diff = sum(r["diff"] for r in sheet)

    for row in sheet:
        code = row["code"]
        if not isinstance(code, int):
            print(f"\n  ⚠️  كود '{code}' - رحلة خارجية، يتم تجاهلها")
            continue

        db_trip = trips_db.get(code)

        if not db_trip:
            print(f"\n  ❌ كود #{code} ({row['dest']}) - غير موجود في قاعدة البيانات!")
            not_found.append(row)
            continue

        # السعر في النظام
        system_price = db_trip.get("estimated_price") or 0
        final_price   = db_trip.get("final_price") or 0
        effective_price = final_price if final_price > 0 else system_price

        # طريقة الدفع - نكتشفها من admin_notes فقط (عمود payment_method غير موجود)
        pay_method = ""
        admin_notes = db_trip.get("admin_notes") or ""
        is_postpaid_db = (
            "postpaid" in admin_notes.lower()
            or "آجل" in admin_notes
            or "اجل" in admin_notes
        )

        # الـ vendor_transactions
        vt_entries = vt_by_trip.get(code, [])
        vt_postpaid_amount = sum(v["amount"] for v in vt_entries if v.get("transaction_type") in ["deferred_credit", "postpaid_pending"])
        vt_types = [v.get("transaction_type") for v in vt_entries]

        status_icon = "✅" if db_trip["status"] == "completed" else "🔄" if db_trip["status"] in ["driver_assigned","trip_ended"] else "⏳"

        print(f"\n  {status_icon} كود #{code} | {row['dest']}")
        print(f"      المكتب  → تحصيل: {row['collected']} EGP | فارق: {row['diff']} EGP | آجل: {row['postpaid']} EGP")
        print(f"      النظام  -> estimated: {system_price} | final: {final_price} | status: {db_trip['status']}")
        print(f"      الدفع   -> هل آجل في النظام؟ {'نعم' if is_postpaid_db else 'لا'} | vendor_id: {db_trip.get('vendor_id','لا شيء')}")
        print(f"      vendor_transactions: {vt_types or 'لا شيء'} | مبلغ: {vt_postpaid_amount}")

        # فحص الآجل
        if row["postpaid"] > 0:
            if not is_postpaid_db:
                issues.append({
                    "code": code,
                    "issue": "الرحلة آجل عند المكتب لكن النظام لا يعرفها كآجل",
                    "ops_postpaid": row["postpaid"],
                    "system_postpaid": vt_postpaid_amount,
                })
                postpaid_missing.append(row)
                print(f"      🚨 مشكلة: المكتب يسجلها آجل {row['postpaid']} EGP لكن النظام لا يعرفها!")
            elif vt_postpaid_amount == 0:
                issues.append({
                    "code": code,
                    "issue": "الرحلة آجل في النظام لكن لم يُسجَّل vendor_transactions",
                    "ops_postpaid": row["postpaid"],
                    "system_postpaid": 0,
                })
                postpaid_missing.append(row)
                print(f"      ⚠️  مشكلة: الرحلة آجل لكن لم يُسجَّل في vendor_transactions!")
            else:
                postpaid_ok.append(row)
                diff_amount = row["postpaid"] - vt_postpaid_amount
                if abs(diff_amount) > 10:
                    print(f"      ⚠️  فرق في مبلغ الآجل: المكتب={row['postpaid']} | النظام={vt_postpaid_amount} | فرق={diff_amount}")
                else:
                    print(f"      ✅ مبلغ الآجل متطابق")

        # فحص فارق السعر
        if row["collected"] > 0 and effective_price > 0:
            price_diff = effective_price - row["collected"]
            if abs(price_diff) > 50:
                issues.append({
                    "code": code,
                    "issue": f"فرق في السعر: النظام={effective_price} | المكتب={row['collected']} | فرق={price_diff}",
                    "ops_postpaid": row["postpaid"],
                    "system_postpaid": vt_postpaid_amount,
                })
                print(f"      ❌ فرق سعر: النظام={effective_price} | المكتب={row['collected']} | فرق={price_diff}")

# ===== ملخص الورقتين =====
print("\n" + "=" * 80)
print("📊 ملخص الأرقام الإجمالية")
print("=" * 80)

# الورقة 1
s1_total_postpaid = sum(r["postpaid"] for r in sheet1)
s1_total_diff     = sum(r["diff"]     for r in sheet1)
s1_total_collected= sum(r["collected"] for r in sheet1)

# الورقة 2
s2_total_postpaid = sum(r["postpaid"] for r in sheet2)
s2_total_diff     = sum(r["diff"]     for r in sheet2)
s2_total_collected= sum(r["collected"] for r in sheet2)

print(f"\nالورقة 1 (9-11 يونيو):")
print(f"  شغل آجل:       {s1_total_postpaid} EGP (المكتب: 6200)")
print(f"  فرق تحصيل:     {s1_total_diff}     EGP (المكتب: 2100)")
print(f"  إجمالي تحصيل:  {s1_total_collected} EGP")
print(f"  إجمالي عمليات المكتب: {s1_total_postpaid + s1_total_diff} EGP (المكتب: 8300)")

print(f"\nالورقة 2 (7-8 يونيو):")
print(f"  شغل آجل:       {s2_total_postpaid} EGP (المكتب: 9700)")
print(f"  فرق تحصيل:     {s2_total_diff}     EGP (المكتب: 3700)")
print(f"  إجمالي تحصيل:  {s2_total_collected} EGP")
print(f"  إجمالي عمليات المكتب: {s2_total_postpaid + s2_total_diff} EGP (المكتب: 13400)")

# ===== ملخص المشاكل =====
print("\n" + "=" * 80)
print("🚨 ملخص المشاكل المكتشفة")
print("=" * 80)

if not issues:
    print("✅ لا توجد مشاكل!")
else:
    print(f"\n❌ عدد المشاكل المكتشفة: {len(issues)}")
    for i, issue in enumerate(issues, 1):
        print(f"\n  {i}. كود #{issue.get('code')} → {issue['issue']}")

print(f"\n📌 رحلات آجل لم يُسجَّل مبلغها في النظام: {len(postpaid_missing)}")
for r in postpaid_missing:
    print(f"   - #{r['code']} | {r['dest']} | آجل = {r['postpaid']} EGP")

print(f"\n📌 رحلات غير موجودة في قاعدة البيانات: {len(not_found)}")
for r in not_found:
    print(f"   - #{r['code']} | {r['dest']}")

# ===== جلب بيانات vendor_transactions الحالية للتشغيل =====
print("\n" + "=" * 80)
print("💾 سجل vendor_transactions الحالي لهذه الرحلات")
print("=" * 80)

for code in numeric_codes:
    vts = vt_by_trip.get(code, [])
    if vts:
        print(f"\n  رحلة #{code}:")
        for vt in vts:
            print(f"    - type={vt['transaction_type']} | amount={vt['amount']} | desc={vt.get('description','')[:60]}")
    # else:
    #     print(f"  رحلة #{code}: لا توجد حركات مالية")

print("\n✅ اكتمل التحليل")
