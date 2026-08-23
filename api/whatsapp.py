from http.server import BaseHTTPRequestHandler
import json
import os
import urllib.parse
import requests

FB_VERIFY_TOKEN = os.environ.get("FB_VERIFY_TOKEN", "messenger_secret_24seven")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://khskudtxbypohvnreloi.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

def get_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal"
    }

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
        """WhatsApp Cloud API Webhook Verification GET"""
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
            self.wfile.write(json.dumps({"error": "Forbidden"}).encode('utf-8'))

    def do_POST(self):
        """WhatsApp Cloud API Incoming Messages POST"""
        try:
            content_len = int(self.headers.get('Content-Length', 0))
            post_body = self.rfile.read(content_len).decode('utf-8')
            data = json.loads(post_body) if post_body else {}

            for entry in data.get('entry', []):
                for change in entry.get('changes', []):
                    val = change.get('value', {})
                    messages = val.get('messages', [])
                    for msg in messages:
                        sender_phone = msg.get('from', '')
                        msg_text = msg.get('text', {}).get('body', '')
                        if sender_phone and msg_text and SUPABASE_KEY:
                            payload = {
                                "channel": "whatsapp",
                                "sender_id": str(sender_phone),
                                "sender_name": f"عميل واتساب (+{sender_phone})",
                                "message_text": msg_text,
                                "is_from_admin": False,
                                "read_by_admin": False
                            }
                            requests.post(f"{SUPABASE_URL}/rest/v1/omnichannel_messages", headers=get_headers(), json=payload, timeout=5)

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
