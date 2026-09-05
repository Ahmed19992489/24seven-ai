from http.server import BaseHTTPRequestHandler
import json
import os
import urllib.parse
import requests

FB_VERIFY_TOKEN = os.environ.get("FB_VERIFY_TOKEN", "messenger_secret_24seven")
NEON_CONN_STR = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL") or "postgresql://neondb_owner:npg_WFZmc7X1YEMQ@ep-falling-glade-a5v7q460-pooler.us-east-2.aws.neon.tech/neondb?sslmode=require"
NEON_HTTP_URL = "https://ep-falling-glade-a5v7q460-pooler.us-east-2.aws.neon.tech/sql"

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
                        if sender_phone and msg_text:
                            sql = "INSERT INTO omnichannel_messages (channel, sender_id, sender_name, message_text, is_from_admin, read_by_admin) VALUES ($1, $2, $3, $4, $5, $6)"
                            params = ["whatsapp", str(sender_phone), f"عميل واتساب (+{sender_phone})", str(msg_text), False, False]
                            requests.post(
                                NEON_HTTP_URL,
                                headers={"Neon-Connection-String": NEON_CONN_STR},
                                json={"query": sql, "params": params},
                                timeout=8
                            )

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
