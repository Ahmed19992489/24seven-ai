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

def save_to_supabase(sender_id, sender_name, text, is_admin=False):
    if not SUPABASE_KEY:
        return
    try:
        payload = {
            "channel": "instagram",
            "sender_id": str(sender_id),
            "sender_name": sender_name,
            "message_text": text,
            "is_from_admin": is_admin,
            "read_by_admin": is_admin
        }
        requests.post(f"{SUPABASE_URL}/rest/v1/omnichannel_messages", headers=get_headers(), json=payload, timeout=5)
    except Exception as e:
        print(f"Error saving IG to Supabase: {e}")

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
                    message = event.get('message', {})
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
