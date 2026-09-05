from http.server import BaseHTTPRequestHandler
import json
import os
import urllib.parse
import requests

# 🔑 Config & Credentials via Environment Variables
FB_PAGE_TOKEN = os.environ.get("FB_PAGE_TOKEN") or "EAAPDbwUyvY0BQrm6ZB9qb62LU9hI50ZC9QOfZAO3VPA7ZCSnFSRMCb2kouBRkXu4LiVmRU2ydv1vLl00kKmgTFMN5ULJOpImor7i8oITjicjIjWiOLxTL7yltYrlF0RLxcdU6UNOaIdqo4Ouv0BnQ79OK2sgSLpHY9ZCQs4iRIxcpjnoxr8EWpV4FSgGTzgZDZD"
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

def save_to_supabase(sender_id, sender_name, text, is_admin=False):
    try:
        sql = "INSERT INTO omnichannel_messages (channel, sender_id, sender_name, message_text, is_from_admin, read_by_admin) VALUES ($1, $2, $3, $4, $5, $6)"
        params = ["instagram", str(sender_id), str(sender_name), str(text), bool(is_admin), bool(is_admin)]
        requests.post(
            NEON_HTTP_URL,
            headers={"Neon-Connection-String": NEON_CONN_STR},
            json={"query": sql, "params": params},
            timeout=8
        )
    except Exception as e:
        print(f"Error saving IG to Neon: {e}")

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
        """Instagram Webhook Verification GET"""
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
        """Instagram Incoming Messages POST"""
        try:
            content_len = int(self.headers.get('Content-Length', 0))
            post_body = self.rfile.read(content_len).decode('utf-8')
            data = json.loads(post_body) if post_body else {}

            for entry in data.get('entry', []):
                events = entry.get('messaging', []) or entry.get('standby', [])
                for event in events:
                    if 'delivery' in event or 'read' in event:
                        continue

                    sender_id = str(event.get('sender', {}).get('id', ''))
                    message = event.get('message', {}) or event.get('message_edit', {})

                    if message.get('is_echo'):
                        # Admin sent reply from Instagram app / Meta Business Suite
                        admin_text = message.get('text', '').strip()
                        if not admin_text and 'attachments' in message:
                            att = message['attachments'][0]
                            admin_text = f"📎 [{att.get('type')}] {att.get('payload', {}).get('url', '')}"
                        
                        recipient_id = str(event.get('recipient', {}).get('id', ''))
                        if admin_text and recipient_id:
                            save_to_supabase(recipient_id, "فريق 24Seven", admin_text, is_admin=True)
                        continue

                    text = message.get('text')
                    if not text and 'attachments' in message:
                        att = message['attachments'][0]
                        text = f"📎 [{att.get('type')}] {att.get('payload', {}).get('url', '')}"

                    if sender_id and text:
                        save_to_supabase(sender_id, "عميل انستجرام", text, is_admin=False)

            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write("EVENT_RECEIVED".encode('utf-8'))
        except Exception as e:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode('utf-8'))
