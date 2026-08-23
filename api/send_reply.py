from http.server import BaseHTTPRequestHandler
import json
import os
import requests

FB_PAGE_TOKEN = os.environ.get("FB_PAGE_TOKEN", "")
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
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def do_OPTIONS(self):
        self.send_response(200)
        self._send_cors_headers()
        self.end_headers()

    def do_POST(self):
        try:
            content_len = int(self.headers.get('Content-Length', 0))
            post_body = self.rfile.read(content_len).decode('utf-8')
            data = json.loads(post_body) if post_body else {}

            channel = data.get("channel", "messenger")
            recipient_id = data.get("recipient_id") or data.get("sender_id") or data.get("to")
            message_text = data.get("message") or data.get("text")
            sender_name = data.get("admin_name") or "Admin"

            if not recipient_id or not message_text:
                self.send_response(400)
                self._send_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Missing recipient_id or message"}).encode('utf-8'))
                return

            if channel in ["messenger", "facebook"]:
                if not FB_PAGE_TOKEN:
                    self.send_response(500)
                    self._send_cors_headers()
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": "FB_PAGE_TOKEN not configured"}).encode('utf-8'))
                    return

                # Send via Facebook Graph API
                url = f"https://graph.facebook.com/v18.0/me/messages?access_token={FB_PAGE_TOKEN}"
                payload = {
                    "recipient": {"id": str(recipient_id)},
                    "messaging_type": "RESPONSE",
                    "message": {"text": message_text}
                }
                r = requests.post(url, json=payload, timeout=8)
                fb_res = r.json()

                if r.status_code == 200:
                    # Save to Supabase
                    if SUPABASE_KEY:
                        sb_payload = {
                            "channel": "messenger",
                            "sender_id": str(recipient_id),
                            "sender_name": sender_name,
                            "message_text": message_text,
                            "is_from_admin": True,
                            "read_by_admin": True
                        }
                        requests.post(f"{SUPABASE_URL}/rest/v1/omnichannel_messages", headers=get_headers(), json=sb_payload, timeout=5)

                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self._send_cors_headers()
                    self.end_headers()
                    self.wfile.write(json.dumps({"status": "success", "fb_response": fb_res}).encode('utf-8'))
                else:
                    self.send_response(500)
                    self.send_header("Content-Type", "application/json")
                    self._send_cors_headers()
                    self.end_headers()
                    self.wfile.write(json.dumps({"status": "error", "fb_error": fb_res}).encode('utf-8'))
            else:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self._send_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps({"error": f"Channel {channel} not supported on cloud serverless"}).encode('utf-8'))

        except Exception as e:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode('utf-8'))
