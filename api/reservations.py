from http.server import BaseHTTPRequestHandler
import urllib.parse
import json
import os
import requests

NEON_CONN_STR = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL") or "postgresql://neondb_owner:npg_VM4tSBwN5PGd@ep-plain-rice-auzortld-pooler.c-10.us-east-1.aws.neon.tech/neondb?sslmode=require"
NEON_HTTP_URL = "https://ep-plain-rice-auzortld-pooler.c-10.us-east-1.aws.neon.tech/sql"

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
