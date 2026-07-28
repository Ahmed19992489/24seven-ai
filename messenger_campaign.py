import requests
import json
import sys
import os
import time

sys.stdout.reconfigure(encoding='utf-8')

# =====================================================
# ⚙️ إعدادات حملة ماسنجر 24Seven
# =====================================================
SUPABASE_URL = "https://wtjwzqvmwnbvjxnmweqq.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Ind0and6cXZtd25idmp4bm13ZXFxIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3MTQ2NTQwMywiZXhwIjoyMDg3MDQxNDAzfQ.WYNflQntWBCHXDnxFf2C1X1IerYZtMfMT6p6P4Dx0Vg"
FB_PAGE_TOKEN = "EAAPDbwUyvY0BRN0VW4bIHPLRpeA7qHqK5TyFpNxJ8fuFcvVCshuBwZC52F59Q6oNH671nLZBbAiEsGSB55Vq0sHjyMIB4QNStzt6sFxRL7ImzttrnuFkHVTYWGZC0J2MgbBGfqo3dOi7Wo5QagQ7pY3vhZAztfKZBhNZCxGrVeGRIqz7pUkHHC2iM4ZA0mDje9oEXZCm"

HEADERS_SB = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

def fetch_messenger_customers():
    """جلب كافة عملاء ماسنجر الفريدين من قاعدة البيانات"""
    url = f"{SUPABASE_URL}/rest/v1/omnichannel_messages?channel=eq.messenger&select=sender_id,sender_name&order=created_at.desc&limit=2000"
    r = requests.get(url, headers=HEADERS_SB)
    clients = {}
    if r.status_code == 200:
        msgs = r.json()
        for m in msgs:
            sid = m.get("sender_id")
            sname = m.get("sender_name") or "Messenger User"
            if sid and sid not in clients and sname not in ["Admin", "Bot", "ش"]:
                clients[sid] = sname
    return clients

def send_messenger_message(recipient_id, text_body):
    """إرسال رسالة ماسنجر للعميل عبر فيسبوك API"""
    url = f"https://graph.facebook.com/v18.0/me/messages?access_token={FB_PAGE_TOKEN}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "recipient": {"id": str(recipient_id)},
        "message": {"text": text_body}
    }
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=15)
        if r.status_code == 200:
            return True, "OK"
        else:
            return False, r.text
    except Exception as e:
        return False, str(e)

def log_to_supabase(sender_id, sender_name, text_body):
    """حفظ الرسالة المرسلة في Supabase لتظهر في لوحة المحادثات"""
    url = f"{SUPABASE_URL}/rest/v1/omnichannel_messages"
    payload = {
        "channel": "messenger",
        "sender_id": str(sender_id),
        "sender_name": sender_name,
        "message_text": text_body,
        "is_from_admin": True,
        "read_by_admin": True
    }
    try:
        requests.post(url, headers=HEADERS_SB, json=payload, timeout=5)
    except Exception as e:
        pass

def main():
    print("=" * 70)
    print("📢 24Seven Messenger Broadcast Campaign Tool")
    print("   أداة أتمتة وإرسال الحملات الإعلانية لعملاء الفيس بوك ماسنجر")
    print("=" * 70 + "\n")

    print("🔍 جلب قائمة عملاء ماسنجر من قاعدة البيانات...")
    customers = fetch_messenger_customers()
    total_customers = len(customers)

    if total_customers == 0:
        print("❌ لم يتم العثور على أي عملاء ماسنجر سابقين في قاعدة البيانات.")
        return

    print(f"✅ تم العثور على ({total_customers}) عميل فريد تواصلوا معنا على الماسنجر!\n")

    # فحص وجود نص حملة جاهز في ملف campaign_message.txt
    msg_file = os.path.join(os.path.dirname(__file__), "campaign_message.txt")
    campaign_text = ""
    if os.path.exists(msg_file):
        try:
            with open(msg_file, "r", encoding="utf-8") as f:
                campaign_text = f.read().strip()
        except Exception:
            pass

    if campaign_text:
        print("📝 تم العثور على نص الحملة من ملف 'campaign_message.txt':")
        print("-" * 50)
        print(campaign_text)
        print("-" * 50)
    else:
        print("📝 أدخل نص الرسالة المراد إرسالها لجميع العملاء (أو اترك السطر فارغاً للإلغاء):")
        print("(يمكنك أيضاً حفظ الرسالة داخل ملف باسم campaign_message.txt في نفس المجلد)")
        print("-" * 50)
        lines = []
        try:
            while True:
                line = input()
                if not line and lines: # سطر فارغ للنهاية
                    break
                lines.append(line)
        except EOFError:
            pass
        campaign_text = "\n".join(lines).strip()

    if not campaign_text:
        print("⚠️ تم إلغاء الحملة لعدم وجود نص رسالة.")
        return

    print(f"\n🚀 هل أنت متأكد من بدء إرسال الحملة لـ ({total_customers}) عميل ماسنجر؟")
    print("   اضغط Enter للبدء أو Ctrl+C للإلغاء...")
    try:
        input()
    except (KeyboardInterrupt, EOFError):
        print("\n❌ تم إلغاء الحملة بناءً على طلبك.")
        return

    print("\n" + "=" * 50)
    print("⏳ جاري بدء إرسال الحملة...")
    print("=" * 50)

    success_count = 0
    fail_count = 0

    for idx, (sid, sname) in enumerate(customers.items(), 1):
        print(f"[{idx}/{total_customers}] ✉️ إرسال إلى: {sname} ({sid})... ", end="", flush=True)
        ok, res_text = send_messenger_message(sid, campaign_text)
        if ok:
            success_count += 1
            print("✅ تم الإرسال")
            log_to_supabase(sid, sname, campaign_text)
        else:
            fail_count += 1
            print(f"❌ فشل ({res_text[:60]})")

        # فاصل أمني (1.5 ثانية) لمنع حظر الفيس بوك Rate Limit
        time.sleep(1.5)

    print("\n" + "=" * 70)
    print("🎉 اكتملت الحملة الإعلانية بنجاح!")
    print(f"   ✅ تم الإرسال بنجاح: {success_count}")
    print(f"   ❌ فشل الإرسال: {fail_count}")
    print(f"   📊 الإجمالي: {total_customers}")
    print("=" * 70)

if __name__ == '__main__':
    main()
