from http.server import BaseHTTPRequestHandler
import json
import os
import urllib.parse
import requests

# 🔑 Config & Credentials via Environment Variables
FB_PAGE_TOKEN = os.environ.get("FB_PAGE_TOKEN", "")
FB_VERIFY_TOKEN = os.environ.get("FB_VERIFY_TOKEN", "messenger_secret_24seven")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://khskudtxbypohvnreloi.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")

def get_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal"
    }

def get_fb_name(sender_id):
    if not FB_PAGE_TOKEN:
        return "عميل فيسبوك"
    try:
        url = "https://graph.facebook.com/v18.0/me/conversations"
        params = {
            "access_token": FB_PAGE_TOKEN,
            "user_id": str(sender_id),
            "fields": "participants"
        }
        r = requests.get(url, params=params, timeout=4)
        if r.status_code == 200:
            data = r.json()
            for conv in data.get('data', []):
                for p in conv.get('participants', {}).get('data', []):
                    if str(p.get('id')) == str(sender_id):
                        name = p.get('name', '').strip()
                        if name:
                            return name
    except Exception as e:
        print(f"Error in conversations name lookup: {e}")

    try:
        url = f"https://graph.facebook.com/v18.0/{sender_id}?fields=first_name,last_name,name&access_token={FB_PAGE_TOKEN}"
        r = requests.get(url, timeout=4)
        if r.status_code == 200:
            d = r.json()
            name = d.get('name') or f"{d.get('first_name', '')} {d.get('last_name', '')}".strip()
            if name: return name
    except Exception:
        pass
    return "عميل فيسبوك"

def send_fb_reply(recipient_id, text):
    if not FB_PAGE_TOKEN:
        return False
    try:
        url = f"https://graph.facebook.com/v18.0/me/messages?access_token={FB_PAGE_TOKEN}"
        payload = {
            "recipient": {"id": recipient_id},
            "messaging_type": "RESPONSE",
            "message": {"text": text}
        }
        r = requests.post(url, json=payload, timeout=5)
        return r.status_code == 200
    except Exception as e:
        print(f"Error sending FB reply: {e}")
        return False

def save_to_supabase(sender_id, sender_name, text, is_admin=False):
    if not SUPABASE_KEY:
        return
    try:
        payload = {
            "channel": "messenger",
            "sender_id": str(sender_id),
            "sender_name": sender_name,
            "message_text": text,
            "is_from_admin": is_admin,
            "read_by_admin": is_admin
        }
        requests.post(f"{SUPABASE_URL}/rest/v1/omnichannel_messages", headers=get_headers(), json=payload, timeout=5)
    except Exception as e:
        print(f"Error saving to Supabase: {e}")

def get_ai_reply(client_text, sender_name="يا فندم"):
    # 1. Quick rule-based responses for common questions
    t = client_text.lower().strip()
    if any(w in t for w in ["سلام", "مرحبا", "مساء الخير", "صباح الخير", "اهلا", "أهلا", "ازيك", "ازيكم", "السلام عليكم"]):
        return f"أهلاً بحضرتك يا {sender_name} في 24Seven لخدمات الليموزين والنقل السياحي 🚗✨\nيسعدنا خدمتك، ممكن توضح لنا تفاصيل رحلتك (مكان التحرك، مكان الوصول، والتاريخ) وسنوافيك بالأسعار فوراً؟"
    if any(w in t for w in ["اسعار", "أسعار", "كام", "بكام", "تكلفة", "سعر", "price", "cost"]):
        return f"تحت أمرك يا فندم 🌹 لتحديد أفضل سعر لرحلتك، يرجى تزويدنا بالتفاصيل:\n📍 مكان التحرك\n📍 مكان الوصول\n📅 تاريخ وموعد الرحلة\n👥 عدد الأفراد ونوع السيارة المطلوبة."
    if any(w in t for w in ["مطار", "airport", "حجز", "عايز احجز", "حجز رحلة"]):
        return "أهلاً بك يا فندم ✈️ متوفر لدينا أحدث السيارات لخدمات المطار وجميع المحافظات 24 ساعة.\nمن فضلك أرسل موعد الرحلة وتفاصيل المسار لتأكيد الحجز فوراً."

    # 2. Use Groq AI if key is set
    try:
        if GROQ_API_KEY:
            url = 'https://api.groq.com/openai/v1/chat/completions'
            headers = {
                'Authorization': f'Bearer {GROQ_API_KEY}',
                'Content-Type': 'application/json'
            }
            prompt = (
                "أنت مساعد خدمة عملاء ذكي ولبق جداً لشركة ليموزين ونقل سياحي اسمها '24Seven Limousine' في مصر.\n"
                "خدماتنا: رحلات المطار (القاهرة، برج العرب، سفنكس)، رحلات بين المحافظات، سيارات سيدان وH1 وفانات عائلية.\n"
                "رد على العميل بأسلوب محترف، ودود، مصري لطيف، واطلب منه تفاصيل الرحلة (التحرك، الوصول، والموعد).\n"
                "اجعل الرد مختصراً في 2-3 أسطر فقط مع إيموجي لطيف."
            )
            payload = {
                'model': 'allam-2-7b',
                'messages': [
                    {'role': 'system', 'content': prompt},
                    {'role': 'user', 'content': client_text}
                ],
                'max_tokens': 150,
                'temperature': 0.3
            }
            r = requests.post(url, headers=headers, json=payload, timeout=5)
            if r.status_code == 200:
                reply = r.json()['choices'][0]['message']['content'].strip()
                if reply: return reply
    except Exception:
        pass

    return f"أهلاً بحضرتك يا فندم 🌹 تم استلام رسالتك، وسيقوم مسؤول الحجوزات بالرد عليك وتأكيد كافة التفاصيل في أقرب وقت. ✨"

class handler(BaseHTTPRequestHandler):
    def _send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def do_OPTIONS(self):
        self.send_response(200)
        self._send_cors_headers()
        self.end_headers()

    def do_GET(self):
        """Meta Webhook Verification GET"""
        parsed_url = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed_url.query)
        
        mode = query.get("hub.mode", [""])[0]
        token = query.get("hub.verify_token", [""])[0]
        challenge = query.get("hub.challenge", [""])[0]

        if mode == "subscribe" and token in [FB_VERIFY_TOKEN, "messenger_secret_24seven", "24seven_secret_token"]:
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(challenge.encode('utf-8'))
        else:
            self.send_response(403)
            self.send_header("Content-Type", "application/json")
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Forbidden - invalid verify token"}).encode('utf-8'))

    def do_POST(self):
        """Meta Incoming Messages POST"""
        try:
            content_len = int(self.headers.get('Content-Length', 0))
            post_body = self.rfile.read(content_len).decode('utf-8')
            data = json.loads(post_body) if post_body else {}

            if data.get('object') in ['page', 'instagram']:
                for entry in data.get('entry', []):
                    events = entry.get('messaging', []) or entry.get('standby', [])
                    for event in events:
                        if 'delivery' in event or 'read' in event:
                            continue

                        sender_id = str(event.get('sender', {}).get('id', ''))
                        message = event.get('message', {}) or event.get('message_edit', {})
                        
                        if message.get('is_echo'):
                            # Admin sent from Facebook Page directly
                            admin_text = message.get('text', '').strip()
                            recipient_id = str(event.get('recipient', {}).get('id', ''))
                            if admin_text and recipient_id:
                                save_to_supabase(recipient_id, "Admin", admin_text, is_admin=True)
                            continue

                        text = message.get('text')
                        if not text and 'attachments' in message:
                            att = message['attachments'][0]
                            text = f"📎 [{att.get('type')}] {att.get('payload', {}).get('url', '')}"
                        elif not text and 'postback' in event:
                            text = event['postback'].get('payload')

                        if sender_id and text:
                            # 1. Resolve sender name
                            sender_name = get_fb_name(sender_id)

                            # 2. Save client message to Supabase for human moderators
                            save_to_supabase(sender_id, sender_name, text, is_admin=False)

            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write("EVENT_RECEIVED".encode('utf-8'))
        except Exception as e:
            self.send_response(200) # Always return 200 to Meta to prevent retry storms
            self.send_header("Content-Type", "application/json")
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode('utf-8'))
