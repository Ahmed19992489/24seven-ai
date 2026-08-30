from http.server import BaseHTTPRequestHandler
import urllib.parse
import json
import os
import requests

NEON_CONN_STR = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL") or "postgresql://neondb_owner:npg_VM4tSBwN5PGd@ep-plain-rice-auzortld-pooler.c-10.us-east-1.aws.neon.tech/neondb?sslmode=require"
NEON_HTTP_URL = "https://ep-plain-rice-auzortld-pooler.c-10.us-east-1.aws.neon.tech/sql"
APPS_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbyInsDC7MKcsfJWVwYpl5pFmiDp5XdkSF5Pi1MSJfSbKQPTp0M8F3aUhb9QHmBdbYutjA/exec"

class handler(BaseHTTPRequestHandler):
    def _send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, ngrok-skip-browser-warning")

    def do_OPTIONS(self):
        self.send_response(200)
        self._send_cors_headers()
        self.end_headers()

    def do_GET(self):
        query_components = {}
        if "?" in self.path:
            try:
                query_str = self.path.split("?", 1)[1]
                query_components = urllib.parse.parse_qs(query_str)
            except Exception:
                pass

        date_val = query_components.get("date", [None])[0]
        query_val = query_components.get("query", [None])[0]
        limit_val = int(query_components.get("limit", [300])[0])

        results = []
        source = "neon_http_api"

        try:
            sql = """
                SELECT id, sheet_row, trip_date, trip_time, customer_name, customer_phone,
                       whatsapp_num, pickup_address, dropoff_address, passengers, bags, car_type,
                       cost, email, notes, trip_type, booking_employee, status, sql_server_id,
                       modified_driver_name, modified_driver_phone, driver_msg_status,
                       confirm_msg_status, client_decision, location_link, rating_stars,
                       trip_status, created_at
                FROM google_reservations
                WHERE 1=1
            """
            params = []
            if date_val:
                d_clean = date_val.replace('/', '-').strip()
                d_slash = date_val.replace('-', '/').strip()
                idx1 = len(params) + 1
                idx2 = len(params) + 2
                idx3 = len(params) + 3
                sql += f" AND (trip_date = ${idx1} OR trip_date = ${idx2} OR trip_date LIKE ${idx3})"
                params.extend([d_clean, d_slash, f"%{d_clean}%"])

            if query_val:
                q_clean = query_val.strip()
                idx_q = len(params) + 1
                sql += f" AND (customer_name ILIKE ${idx_q} OR customer_phone ILIKE ${idx_q} OR pickup_address ILIKE ${idx_q} OR dropoff_address ILIKE ${idx_q})"
                params.append(f"%{q_clean}%")

            idx_lim = len(params) + 1
            sql += f" ORDER BY trip_time ASC, id DESC LIMIT ${idx_lim};"
            params.append(limit_val)

            r = requests.post(
                NEON_HTTP_URL,
                headers={"Neon-Connection-String": NEON_CONN_STR},
                json={"query": sql, "params": params},
                timeout=10
            )

            if r.status_code == 200:
                rows = r.json().get("rows", [])
                for d in rows:
                    d["estimated_price"] = d.get("cost") or 0
                    d["manual_client_name"] = d.get("customer_name") or ""
                    d["client_phone"] = d.get("customer_phone") or ""
                    d["pickup_location"] = d.get("pickup_address") or ""
                    d["dropoff_location"] = d.get("dropoff_address") or ""
                    results.append(d)
            else:
                source = f"neon_error_{r.status_code}"

        except Exception as e_neon:
            source = f"error: {e_neon}"

        payload = json.dumps({
            "status": "ok",
            "source": source,
            "count": len(results),
            "data": results
        }, ensure_ascii=False).encode('utf-8')

        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(payload)

    def do_POST(self):
        try:
            content_len = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_len).decode('utf-8')
            data = json.loads(body) if body else {}

            action = data.get("action")
            sheet_row = data.get("sheetRow") or data.get("sheet_row")
            sql_id = data.get("sqlId") or data.get("sql_id")
            web_id = data.get("webId") or data.get("web_id")
            driver_name = data.get("driverName") or data.get("driver_name", "")
            driver_phone = data.get("driverPhone") or data.get("driver_phone", "")

            # 1. تحديث قاعدة بيانات نيون (google_reservations)
            neon_updated = False
            try:
                where_clauses = []
                params = [driver_name, driver_phone]
                if sheet_row:
                    params.append(int(sheet_row))
                    where_clauses.append(f"sheet_row = ${len(params)}")
                if sql_id:
                    params.append(str(sql_id))
                    where_clauses.append(f"sql_server_id = ${len(params)}")
                if web_id and str(web_id).isdigit():
                    params.append(int(web_id))
                    where_clauses.append(f"id = ${len(params)}")

                if where_clauses:
                    update_sql = f"""
                        UPDATE google_reservations 
                        SET modified_driver_name = $1, 
                            modified_driver_phone = $2, 
                            status = 'driver_assigned',
                            updated_at = NOW() 
                        WHERE {' OR '.join(where_clauses)};
                    """
                    r_neon = requests.post(
                        NEON_HTTP_URL,
                        headers={"Neon-Connection-String": NEON_CONN_STR},
                        json={"query": update_sql, "params": params},
                        timeout=10
                    )
                    if r_neon.status_code == 200:
                        neon_updated = True
            except Exception as e_neon:
                print(f"[AssignDriver] Neon update error: {e_neon}")

            # 2. تحديث جوجل شيت مباشرة عبر Google Apps Script من السيرفر
            sheet_synced = False
            sheet_response = None
            try:
                sheet_payload = {
                    "action": "assignDriver",
                    "sheetRow": sheet_row or "",
                    "sqlId": str(sql_id) if sql_id else "",
                    "webId": str(web_id) if web_id else "",
                    "driverName": driver_name,
                    "driverPhone": driver_phone
                }
                r_sheet = requests.post(
                    APPS_SCRIPT_URL,
                    data=json.dumps(sheet_payload),
                    headers={"Content-Type": "text/plain"},
                    timeout=15
                )
                if r_sheet.status_code == 200:
                    sheet_response = r_sheet.json()
                    sheet_synced = sheet_response.get("success", False)
            except Exception as e_sheet:
                print(f"[AssignDriver] Google Sheet sync error: {e_sheet}")

            res_body = json.dumps({
                "status": "success" if (neon_updated or sheet_synced) else "partial",
                "neon_updated": neon_updated,
                "sheet_synced": sheet_synced,
                "sheet_response": sheet_response
            }, ensure_ascii=False).encode('utf-8')

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(res_body)))
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(res_body)

        except Exception as e_main:
            err_body = json.dumps({"status": "error", "message": str(e_main)}).encode('utf-8')
            self.send_response(500)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(err_body)))
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(err_body)
