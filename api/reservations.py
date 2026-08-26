from http.server import BaseHTTPRequestHandler
import urllib.parse
import json
import os
import ssl

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
        query_components = {}
        if "?" in self.path:
            query_str = self.path.split("?", 1)[1]
            query_components = urllib.parse.parse_qs(query_str)

        date_val = query_components.get("date", [None])[0]
        query_val = query_components.get("query", [None])[0]
        limit_val = int(query_components.get("limit", [300])[0])

        results = []
        source = "neon_postgres"

        # 1. Try Neon Postgres
        try:
            import pg8000.native
            
            NEON_USER = os.getenv("PGUSER", "neondb_owner")
            NEON_PASSWORD = os.getenv("PGPASSWORD", "npg_VM4tSBwN5PGd")
            NEON_HOST = os.getenv("PGHOST", "ep-plain-rice-auzortld-pooler.c-10.us-east-1.aws.neon.tech")
            NEON_DB = os.getenv("PGDATABASE", "neondb")

            con = pg8000.native.Connection(
                user=NEON_USER,
                password=NEON_PASSWORD,
                host=NEON_HOST,
                port=5432,
                database=NEON_DB,
                ssl_context=ssl.create_default_context(),
                timeout=8
            )

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
            params = {}
            if date_val:
                d_clean = date_val.replace('/', '-').strip()
                d_slash = date_val.replace('-', '/').strip()
                sql += " AND (trip_date = :d1 OR trip_date = :d2 OR trip_date LIKE :d3)"
                params["d1"] = d_clean
                params["d2"] = d_slash
                params["d3"] = f"%{d_clean}%"

            if query_val:
                q_clean = query_val.strip()
                sql += " AND (customer_name ILIKE :q OR customer_phone ILIKE :q OR pickup_address ILIKE :q OR dropoff_address ILIKE :q)"
                params["q"] = f"%{q_clean}%"

            sql += " ORDER BY trip_time ASC, id DESC LIMIT :lim;"
            params["lim"] = limit_val

            rows = con.run(sql, **params)
            cols = [
                "id", "sheet_row", "trip_date", "trip_time", "customer_name", "customer_phone",
                "whatsapp_num", "pickup_address", "dropoff_address", "passengers", "bags", "car_type",
                "cost", "email", "notes", "trip_type", "booking_employee", "status", "sql_server_id",
                "modified_driver_name", "modified_driver_phone", "driver_msg_status",
                "confirm_msg_status", "client_decision", "location_link", "rating_stars",
                "trip_status", "created_at"
            ]

            for r in rows:
                d = dict(zip(cols, r))
                d["estimated_price"] = d["cost"]
                d["manual_client_name"] = d["customer_name"]
                d["client_phone"] = d["customer_phone"]
                d["pickup_location"] = d["pickup_address"]
                d["dropoff_location"] = d["dropoff_address"]
                if d.get("created_at"):
                    d["created_at"] = str(d["created_at"])
                results.append(d)

            con.close()
        except Exception as e_neon:
            print("Neon error in Vercel function:", e_neon)
            source = "error_fallback"

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(json.dumps({
            "status": "ok",
            "source": source,
            "count": len(results),
            "data": results
        }, ensure_ascii=False).encode('utf-8'))
