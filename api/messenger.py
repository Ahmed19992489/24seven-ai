from http.server import BaseHTTPRequestHandler
import json
import os
import urllib.parse
import requests

# 🔑 Config & Credentials via Environment Variables
FB_PAGE_TOKEN = os.environ.get("FB_PAGE_TOKEN") or "EAAPDbwUyvY0BRN0VW4bIHPLRpeA7qHqK5TyFpNxJ8fuFcvVCshuBwZC52F59Q6oNH671nLZBbAiEsGSB55Vq0sHjyMIB4QNStzt6sFxRL7ImzttrnuFkHVTYWGZC0J2MgbBGfqo3dOi7Wo5QagQ7pY3vhZAztfKZBhNZCxGrVeGRIqz7pUkHHC2iM4ZA0mDje9oEXZCm"
FB_VERIFY_TOKEN = os.environ.get("FB_VERIFY_TOKEN", "messenger_secret_24seven")
def get_neon_creds():
    env_conn = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL")
    if env_conn and "ep-plain-rice" not in env_conn:
        conn = env_conn
    else:
        conn = "postgresql://neondb_owner:npg_WFZmc7X1YEMQ@ep-falling-glade-a5v7q460-pooler.us-east-2.aws.neon.tech/neondb?sslmode=require"
    import re
    m = re.search(r"@([^/]+)/", conn)
    host = m.group(1) if m else "ep-falling-glade-a5v7q460-pooler.us-east-2.aws.neon.tech"
    http_url = f"https://{host}/sql"
    return conn, http_url

NEON_CONN_STR, NEON_HTTP_URL = get_neon_creds()
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")

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

def save_to_supabase(sender_id, sender_name, text, is_admin=False, channel="messenger"):
    try:
        # Prevent duplicate inserts (especially Meta Webhook Echoes)
        check_sql = """
            SELECT id FROM omnichannel_messages 
            WHERE channel = $1 AND sender_id = $2 AND message_text = $3 AND is_from_admin = $4 
            AND created_at >= NOW() - INTERVAL '3 minutes'
            LIMIT 1
        """
        check_params = [channel, str(sender_id), str(text), bool(is_admin)]
        r_chk = requests.post(
            NEON_HTTP_URL,
            headers={"Neon-Connection-String": NEON_CONN_STR},
            json={"query": check_sql, "params": check_params},
            timeout=5
        )
        if r_chk.status_code == 200 and len(r_chk.json().get("rows", [])) > 0:
            return

        sql = "INSERT INTO omnichannel_messages (channel, sender_id, sender_name, message_text, is_from_admin, read_by_admin) VALUES ($1, $2, $3, $4, $5, $6)"
        params = [channel, str(sender_id), str(sender_name), str(text), bool(is_admin), bool(is_admin)]
        requests.post(
            NEON_HTTP_URL,
            headers={"Neon-Connection-String": NEON_CONN_STR},
            json={"query": sql, "params": params},
            timeout=8
        )
    except Exception as e:
        print(f"Error saving to Neon: {e}")

def get_ai_reply(client_text, sender_name="يا فندم"):
    return ""

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

            channel = "instagram" if data.get('object') == 'instagram' else "messenger"

            if data.get('object') in ['page', 'instagram']:
                for entry in data.get('entry', []):
                    events = entry.get('messaging', []) or entry.get('standby', [])
                    for event in events:
                        if 'delivery' in event or 'read' in event:
                            continue

                        sender_id = str(event.get('sender', {}).get('id', ''))
                        message = event.get('message', {}) or event.get('message_edit', {})
                        
                        if message.get('is_echo'):
                            # Admin sent reply from outside (Facebook Page Inbox / Meta Business Suite / Instagram)
                            admin_text = message.get('text', '').strip()
                            if not admin_text and 'attachments' in message:
                                att = message['attachments'][0]
                                admin_text = f"📎 [{att.get('type')}] {att.get('payload', {}).get('url', '')}"
                            
                            recipient_id = str(event.get('recipient', {}).get('id', ''))
                            if admin_text and recipient_id:
                                save_to_supabase(recipient_id, "فريق 24Seven", admin_text, is_admin=True, channel=channel)
                            continue

                        text = message.get('text')
                        if not text and 'attachments' in message:
                            att = message['attachments'][0]
                            att_type = att.get('type', '')
                            att_url = att.get('payload', {}).get('url', '')
                            if att_type in ['image', 'photo']:
                                text = f"MEDIA_IMAGE:{att_url}"
                            elif att_type in ['audio', 'voice']:
                                text = f"MEDIA_AUDIO:{att_url}"
                            elif att_type in ['video']:
                                text = f"MEDIA_VIDEO:{att_url}"
                            else:
                                text = f"📎 [{att_type}] {att_url}"
                        elif not text and 'postback' in event:
                            text = event['postback'].get('payload')

                        if sender_id and text:
                            # 1. Resolve sender name
                            sender_name = get_fb_name(sender_id) if channel == "messenger" else "عميل انستجرام"

                            # 2. Save client message to Supabase for human moderators
                            save_to_supabase(sender_id, sender_name, text, is_admin=False, channel=channel)

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
