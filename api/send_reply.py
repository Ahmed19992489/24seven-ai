from http.server import BaseHTTPRequestHandler
import json
import os
import requests

FB_PAGE_TOKEN = os.environ.get("FB_PAGE_TOKEN") or "EAAPDbwUyvY0BRN0VW4bIHPLRpeA7qHqK5TyFpNxJ8fuFcvVCshuBwZC52F59Q6oNH671nLZBbAiEsGSB55Vq0sHjyMIB4QNStzt6sFxRL7ImzttrnuFkHVTYWGZC0J2MgbBGfqo3dOi7Wo5QagQ7pY3vhZAztfKZBhNZCxGrVeGRIqz7pUkHHC2iM4ZA0mDje9oEXZCm"
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
            sender_name = data.get("admin_name") or data.get("mod_name") or "Admin"

            if not recipient_id or not message_text:
                self.send_response(400)
                self._send_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Missing recipient_id or message"}).encode('utf-8'))
                return

            if channel in ["messenger", "facebook", "instagram"]:
                if not FB_PAGE_TOKEN:
                    self.send_response(500)
                    self._send_cors_headers()
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": "FB_PAGE_TOKEN not configured"}).encode('utf-8'))
                    return

                # Send via Facebook/Instagram Graph API
                url = f"https://graph.facebook.com/v18.0/me/messages?access_token={FB_PAGE_TOKEN}"
                payload = {
                    "recipient": {"id": str(recipient_id)},
                    "messaging_type": "RESPONSE",
                    "message": {"text": message_text}
                }
                r = requests.post(url, json=payload, timeout=8)
                fb_res = r.json()

                # Always save to Neon Database
                try:
                    sql = "INSERT INTO omnichannel_messages (channel, sender_id, sender_name, message_text, is_from_admin, read_by_admin) VALUES ($1, $2, $3, $4, $5, $6)"
                    params = [channel, str(recipient_id), str(sender_name), str(message_text), True, True]
                    requests.post(
                        NEON_HTTP_URL,
                        headers={"Neon-Connection-String": NEON_CONN_STR},
                        json={"query": sql, "params": params},
                        timeout=8
                    )
                except Exception as ne:
                    print(f"Error saving sent reply to Neon: {ne}")

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self._send_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps({"status": "success", "fb_response": fb_res}).encode('utf-8'))

            elif channel == "whatsapp":
                WA_TOKEN = "EAAPDbwUyvY0BQrm6ZB9qb62LU9hI50ZC9QOfZAO3VPA7ZCSnFSRMCb2kouBRkXu4LiVmRU2ydv1vLl00kKmgTFMN5ULJOpImor7i8oITjicjIjWiOLxTL7yltYrlF0RLxcdU6UNOaIdqo4Ouv0BnQ79OK2sgSLpHY9ZCQs4iRIxcpjnoxr8EWpV4FSgGTzgZDZD"
                PHONE_ID = "597129733493778"
                
                clean_phone = str(recipient_id).replace("+", "").replace(" ", "").strip()
                clean_phone = ''.join(c for c in clean_phone if c.isdigit())
                if clean_phone.startswith("01") and len(clean_phone) == 11:
                    clean_phone = "2" + clean_phone
                elif clean_phone.startswith("1") and len(clean_phone) == 10:
                    clean_phone = "20" + clean_phone
                elif clean_phone.startswith("0020"):
                    clean_phone = clean_phone[2:]

                media_url = data.get("media_url")
                media_type = data.get("media_type", "image")
                whatsapp_instance_id = data.get("whatsapp_instance_id") or "692921bb-a5df-451d-8527-e1ee55a736f4"

                wa_res = {}
                is_wa_sent = False
                try:
                    url = f"https://graph.facebook.com/v17.0/{PHONE_ID}/messages"
                    headers = {"Authorization": f"Bearer {WA_TOKEN}", "Content-Type": "application/json"}
                    if media_url:
                        payload = {
                            "messaging_product": "whatsapp",
                            "to": clean_phone,
                            "type": media_type,
                            media_type: {"link": media_url, "caption": message_text if media_type == "image" else ""}
                        }
                    else:
                        payload = {
                            "messaging_product": "whatsapp",
                            "to": clean_phone,
                            "type": "text",
                            "text": {"body": message_text}
                        }
                    r = requests.post(url, json=payload, headers=headers, timeout=8)
                    wa_res = r.json() if r.text else {}
                    if r.status_code == 200:
                        is_wa_sent = True
                except Exception as wa_e:
                    print(f"Meta WA send error: {wa_e}")

                # Save to Neon Database
                try:
                    sql = "INSERT INTO omnichannel_messages (channel, sender_id, sender_name, message_text, is_from_admin, read_by_admin, whatsapp_instance_id) VALUES ($1, $2, $3, $4, $5, $6, $7)"
                    params = [channel, str(recipient_id), str(sender_name), str(message_text), True, True, str(whatsapp_instance_id)]
                    requests.post(
                        NEON_HTTP_URL,
                        headers={"Neon-Connection-String": NEON_CONN_STR},
                        json={"query": sql, "params": params},
                        timeout=8
                    )
                except Exception as ne:
                    print(f"Error saving sent WA reply to Neon: {ne}")

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self._send_cors_headers()
                self.end_headers()
                if is_wa_sent:
                    self.wfile.write(json.dumps({"status": "success", "wa_response": wa_res}).encode('utf-8'))
                else:
                    self.wfile.write(json.dumps({
                        "status": "warning", 
                        "message": "تم تسجيل الرد بنجاح في قاعدة البيانات وجاري تسليمه عبر الواتساب",
                        "wa_response": wa_res
                    }).encode('utf-8'))

            else:
                # Other channels (e.g. support)
                try:
                    sql = "INSERT INTO omnichannel_messages (channel, sender_id, sender_name, message_text, is_from_admin, read_by_admin) VALUES ($1, $2, $3, $4, $5, $6)"
                    params = [channel, str(recipient_id), str(sender_name), str(message_text), True, True]
                    requests.post(
                        NEON_HTTP_URL,
                        headers={"Neon-Connection-String": NEON_CONN_STR},
                        json={"query": sql, "params": params},
                        timeout=8
                    )
                except Exception:
                    pass

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self._send_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps({"status": "success", "message": "Saved message successfully"}).encode('utf-8'))

        except Exception as e:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode('utf-8'))
