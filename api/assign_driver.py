from http.server import BaseHTTPRequestHandler
import json
import os
import requests

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
APPS_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbyInsDC7MKcsfJWVwYpl5pFmiDp5XdkSF5Pi1MSJfSbKQPTp0M8F3aUhb9QHmBdbYutjA/exec"

def sql_quote(val):
    if val is None:
        return "NULL"
    s = str(val).replace("'", "''")
    return f"'{s}'"

class handler(BaseHTTPRequestHandler):
    def _send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, ngrok-skip-browser-warning")
        self.send_header("Access-Control-Allow-Private-Network", "true")

    def do_OPTIONS(self):
        self.send_response(200)
        self._send_cors_headers()
        self.end_headers()

    def do_POST(self):
        try:
            content_len = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_len).decode('utf-8')
            data = json.loads(body) if body else {}

            sheet_row = data.get('sheet_row') or data.get('sheetRow')
            web_id = str(data.get('web_id') or data.get('webId') or '').strip()
            sql_id = str(data.get('sql_id') or data.get('sqlId') or '').strip()
            driver_name = str(data.get('driver_name') or data.get('driverName') or '').strip()
            driver_phone = str(data.get('driver_phone') or data.get('driverPhone') or '').strip()
            driver_msg_status = str(data.get('driver_msg_status') or data.get('driverMsgStatus') or 'تم إرسال بيانات السائق ✅').strip()

            # 1. Update Neon PostgreSQL google_reservations
            neon_updated = False
            try:
                where_clause = ""
                if sheet_row and str(sheet_row).isdigit():
                    where_clause = f"sheet_row = {int(sheet_row)}"
                elif web_id:
                    where_clause = f"id = {sql_quote(web_id)}"
                elif sql_id and sql_id != "0":
                    where_clause = f"sql_server_id = {sql_quote(sql_id)}"

                if where_clause:
                    sql = f"""
                        UPDATE google_reservations
                        SET modified_driver_name = {sql_quote(driver_name)},
                            modified_driver_phone = {sql_quote(driver_phone)},
                            driver_msg_status = {sql_quote(driver_msg_status)},
                            updated_at = NOW()
                        WHERE {where_clause};
                    """
                    r_neon = requests.post(
                        NEON_HTTP_URL,
                        headers={"Neon-Connection-String": NEON_CONN_STR},
                        json={"query": sql},
                        timeout=5
                    )
                    neon_updated = r_neon.status_code == 200
            except Exception as e_neon:
                print(f"Neon update error in assign_driver: {e_neon}")

            # 2. Forward to Google Apps Script (forces sheet_row if available, clears sql_id to prevent collision)
            script_updated = False
            try:
                script_payload = {
                    "action": "assignDriver",
                    "sheet_row": sheet_row or "",
                    "sheetRow": sheet_row or "",
                    "web_id": web_id or "",
                    "webId": web_id or "",
                    "sql_id": "" if sheet_row else (sql_id or ""),
                    "sqlId": "" if sheet_row else (sql_id or ""),
                    "driver_name": driver_name,
                    "driverName": driver_name,
                    "driver_phone": driver_phone,
                    "driverPhone": driver_phone,
                    # حماية العمود 24 (تأكيد الحجز) من المسح
                    "amountPaid": "تم إرسال تأكيد الحجز ✅",
                    "driver_msg_status": driver_msg_status,
                    "driverMsgStatus": driver_msg_status
                }
                r_script = requests.post(
                    APPS_SCRIPT_URL,
                    data=json.dumps(script_payload),
                    headers={"Content-Type": "text/plain"},
                    timeout=15
                )
                if r_script.status_code == 200:
                    script_updated = True
            except Exception as e_script:
                print(f"Apps Script update error in assign_driver: {e_script}")

            response_data = {
                "success": neon_updated or script_updated,
                "neon_updated": neon_updated,
                "script_updated": script_updated,
                "sheet_row": sheet_row,
                "driver_name": driver_name
            }

            self.send_response(200)
            self._send_cors_headers()
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(response_data, ensure_ascii=False).encode('utf-8'))

        except Exception as e:
            self.send_response(500)
            self._send_cors_headers()
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            err_resp = {"success": False, "error": str(e)}
            self.wfile.write(json.dumps(err_resp, ensure_ascii=False).encode('utf-8'))
