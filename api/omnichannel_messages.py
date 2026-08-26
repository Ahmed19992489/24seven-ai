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

        sender_id = query_components.get("sender_id", [None])[0]
        channel = query_components.get("channel", [None])[0]
        limit_val = int(query_components.get("limit", [200])[0])

        results = []
        source = "neon_postgres"

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

            sql = "SELECT id, channel, sender_id, sender_name, message_text, is_from_admin, read_by_admin, created_at FROM omnichannel_messages WHERE 1=1"
            params = {}
            if sender_id:
                sql += " AND sender_id = :sid"
                params["sid"] = str(sender_id).strip()
            if channel:
                sql += " AND channel = :ch"
                params["ch"] = str(channel).strip()

            sql += " ORDER BY created_at DESC LIMIT :lim;"
            params["lim"] = limit_val

            rows = con.run(sql, **params)
            cols = ["id", "channel", "sender_id", "sender_name", "message_text", "is_from_admin", "read_by_admin", "created_at"]
            for r in rows:
                d = dict(zip(cols, r))
                if d.get("created_at"):
                    d["created_at"] = str(d["created_at"])
                results.append(d)

            con.close()
        except Exception as e:
            print("Neon messages error:", e)

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
