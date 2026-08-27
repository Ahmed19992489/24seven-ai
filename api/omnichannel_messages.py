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

        sender_id = query_components.get("sender_id", [None])[0]
        channel = query_components.get("channel", [None])[0]
        limit_val = int(query_components.get("limit", [200])[0])

        results = []
        source = "neon_http_api"

        try:
            sql = "SELECT id, channel, sender_id, sender_name, message_text, is_from_admin, read_by_admin, created_at FROM omnichannel_messages WHERE 1=1"
            params = []
            if sender_id:
                sql += f" AND sender_id = ${len(params)+1}"
                params.append(str(sender_id).strip())
            if channel:
                sql += f" AND channel = ${len(params)+1}"
                params.append(str(channel).strip())

            sql += f" ORDER BY created_at DESC LIMIT ${len(params)+1};"
            params.append(limit_val)

            r = requests.post(
                NEON_HTTP_URL,
                headers={"Neon-Connection-String": NEON_CONN_STR},
                json={"query": sql, "params": params},
                timeout=10
            )

            if r.status_code == 200:
                results = r.json().get("rows", [])
            else:
                source = f"neon_error_{r.status_code}"

        except Exception as e:
            source = f"error: {e}"

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
