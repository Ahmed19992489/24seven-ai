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
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, PUT, DELETE")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, apikey, x-client-info, ngrok-skip-browser-warning")

    def do_OPTIONS(self):
        self.send_response(200)
        self._send_cors_headers()
        self.end_headers()

    def do_POST(self):
        try:
            content_len = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_len).decode('utf-8')
            req = json.loads(body) if body else {}

            action = req.get("action", "select")
            table = req.get("table", "")
            raw_sql = req.get("sql")
            raw_params = req.get("params", [])

            if raw_sql:
                r = requests.post(
                    NEON_HTTP_URL,
                    headers={"Neon-Connection-String": NEON_CONN_STR},
                    json={"query": raw_sql, "params": raw_params},
                    timeout=12
                )
                rows = r.json().get("rows", []) if r.status_code == 200 else []
                self._respond(200, {"status": "ok", "data": rows, "count": len(rows)})
                return

            if not table:
                self._respond(400, {"status": "error", "message": "Table name required"})
                return

            if action == "select":
                select_cols = req.get("select", "*")
                if "(" in select_cols or ":" in select_cols:
                    select_cols = "*"

                sql = f"SELECT {select_cols} FROM {table} WHERE 1=1"
                params = []

                filters = req.get("filters", [])
                for f in filters:
                    op = f.get("op", "eq")
                    col = f.get("col")
                    val = f.get("val")
                    idx = len(params) + 1

                    if op == "eq":
                        sql += f" AND {col} = ${idx}"
                        params.append(val)
                    elif op == "neq":
                        sql += f" AND {col} != ${idx}"
                        params.append(val)
                    elif op == "gt":
                        sql += f" AND {col} > ${idx}"
                        params.append(val)
                    elif op == "gte":
                        sql += f" AND {col} >= ${idx}"
                        params.append(val)
                    elif op == "lt":
                        sql += f" AND {col} < ${idx}"
                        params.append(val)
                    elif op == "lte":
                        sql += f" AND {col} <= ${idx}"
                        params.append(val)
                    elif op == "like" or op == "ilike":
                        sql += f" AND {col} ILIKE ${idx}"
                        params.append(f"%{val}%")
                    elif op == "in":
                        if isinstance(val, list) and len(val) > 0:
                            placeholders = [f"${len(params)+i+1}" for i in range(len(val))]
                            sql += f" AND {col} IN ({','.join(placeholders)})"
                            params.extend(val)
                    elif op == "is":
                        if val is None or val == "null":
                            sql += f" AND {col} IS NULL"
                        else:
                            sql += f" AND {col} IS NOT NULL"
                    elif op == "or":
                        or_parts = str(val).split(",")
                        sub_clauses = []
                        for op_part in or_parts:
                            if ".eq." in op_part:
                                c, v = op_part.split(".eq.", 1)
                                sub_clauses.append(f"{c.strip()} = ${len(params)+1}")
                                params.append(v.strip())
                            elif ".ilike." in op_part:
                                c, v = op_part.split(".ilike.", 1)
                                sub_clauses.append(f"{c.strip()} ILIKE ${len(params)+1}")
                                params.append(v.strip().replace('%', ''))
                        if sub_clauses:
                            sql += f" AND ({' OR '.join(sub_clauses)})"

                order = req.get("order")
                if order:
                    col = order.get("col", "id")
                    asc = "ASC" if order.get("ascending", False) else "DESC"
                    sql += f" ORDER BY {col} {asc}"
                else:
                    sql += " ORDER BY id DESC"

                limit = req.get("limit")
                if limit:
                    sql += f" LIMIT ${len(params)+1}"
                    params.append(int(limit))

                r = requests.post(
                    NEON_HTTP_URL,
                    headers={"Neon-Connection-String": NEON_CONN_STR},
                    json={"query": sql, "params": params},
                    timeout=12
                )
                rows = r.json().get("rows", []) if r.status_code == 200 else []
                self._respond(200, {"status": "ok", "data": rows, "count": len(rows)})

            elif action == "insert":
                records = req.get("data", [])
                if isinstance(records, dict):
                    records = [records]
                if not records:
                    self._respond(200, {"status": "ok", "data": []})
                    return

                inserted_rows = []
                for rec in records:
                    cols = list(rec.keys())
                    vals = list(rec.values())
                    placeholders = [f"${i+1}" for i in range(len(vals))]
                    sql = f"INSERT INTO {table} ({','.join(cols)}) VALUES ({','.join(placeholders)}) RETURNING *;"
                    r = requests.post(
                        NEON_HTTP_URL,
                        headers={"Neon-Connection-String": NEON_CONN_STR},
                        json={"query": sql, "params": vals},
                        timeout=12
                    )
                    if r.status_code == 200:
                        inserted_rows.extend(r.json().get("rows", []))

                self._respond(200, {"status": "ok", "data": inserted_rows})

            elif action == "update":
                data_dict = req.get("data", {})
                eq_dict = req.get("eq", {})
                if not data_dict or not eq_dict:
                    self._respond(400, {"status": "error", "message": "Missing data or eq filter"})
                    return

                set_clauses = []
                params = []
                for k, v in data_dict.items():
                    set_clauses.append(f"{k} = ${len(params)+1}")
                    params.append(v)

                where_clauses = []
                for k, v in eq_dict.items():
                    where_clauses.append(f"{k} = ${len(params)+1}")
                    params.append(v)

                sql = f"UPDATE {table} SET {', '.join(set_clauses)} WHERE {' AND '.join(where_clauses)} RETURNING *;"
                r = requests.post(
                    NEON_HTTP_URL,
                    headers={"Neon-Connection-String": NEON_CONN_STR},
                    json={"query": sql, "params": params},
                    timeout=12
                )
                updated = r.json().get("rows", []) if r.status_code == 200 else []
                self._respond(200, {"status": "ok", "data": updated})

            elif action == "delete":
                eq_dict = req.get("eq", {})
                where_clauses = []
                params = []
                for k, v in eq_dict.items():
                    where_clauses.append(f"{k} = ${len(params)+1}")
                    params.append(v)

                sql = f"DELETE FROM {table} WHERE {' AND '.join(where_clauses)} RETURNING *;"
                r = requests.post(
                    NEON_HTTP_URL,
                    headers={"Neon-Connection-String": NEON_CONN_STR},
                    json={"query": sql, "params": params},
                    timeout=12
                )
                deleted = r.json().get("rows", []) if r.status_code == 200 else []
                self._respond(200, {"status": "ok", "data": deleted})

            else:
                self._respond(400, {"status": "error", "message": f"Unsupported action {action}"})

        except Exception as e:
            self._respond(500, {"status": "error", "message": str(e)})

    def _respond(self, code, obj):
        payload = json.dumps(obj, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(payload)
