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
            decision = str(data.get('decision') or '').strip()
            is_cancelled = data.get('is_cancelled', False) or (decision in ['ملغي', 'رفض'])
            trip_id = data.get('trip_id') or data.get('id')

            neon_ok = False
            # 1. Update Neon PostgreSQL database
            try:
                where_clause = ""
                params = [decision, 'ملغاة' if is_cancelled else 'pending', 'ملغاة' if is_cancelled else 'pending']
                if sheet_row and str(sheet_row).isdigit():
                    params.append(int(sheet_row))
                    where_clause = f"sheet_row = ${len(params)}"
                elif trip_id:
                    params.append(str(trip_id))
                    where_clause = f"id = ${len(params)} OR sql_server_id = ${len(params)}"

                if where_clause:
                    sql = f"""
                        UPDATE google_reservations
                        SET client_decision = $1,
                            trip_status = $2,
                            status = $3,
                            updated_at = NOW()
                        WHERE {where_clause};
                    """
                    r_neon = requests.post(
                        NEON_HTTP_URL,
                        headers={"Neon-Connection-String": NEON_CONN_STR},
                        json={"query": sql, "params": params},
                        timeout=8
                    )
                    if r_neon.status_code == 200:
                        neon_ok = True
            except Exception as e_neon:
                print(f"[update_decision] Neon update error: {e_neon}")

            # 2. Forward to Apps Script
            apps_script_ok = False
            if sheet_row:
                try:
                    payload = {
                        "action": "updateDecision",
                        "sheetRow": int(sheet_row),
                        "decision": decision,
                        "is_cancelled": is_cancelled
                    }
                    r_as = requests.post(APPS_SCRIPT_URL, json=payload, timeout=8)
                    if r_as.status_code == 200:
                        apps_script_ok = True
                except Exception as e_as:
                    print(f"[update_decision] Apps Script error: {e_as}")

            res_body = json.dumps({
                "status": "success",
                "message": "تم تحديث قرار العميل بنجاح",
                "neon_updated": neon_ok,
                "sheet_synced": apps_script_ok
            }, ensure_ascii=False).encode('utf-8')

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(res_body)))
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(res_body)

        except Exception as e:
            err_body = json.dumps({"status": "error", "message": str(e)}).encode('utf-8')
            self.send_response(500)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(err_body)))
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(err_body)
