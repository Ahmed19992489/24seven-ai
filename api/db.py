from http.server import BaseHTTPRequestHandler
import urllib.parse
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

def sql_quote(val):
    if val is None or val == 'null':
        return 'NULL'
    if isinstance(val, bool):
        return 'TRUE' if val else 'FALSE'
    if isinstance(val, (int, float)):
        return str(val)
    s = str(val).replace("'", "''")
    return f"'{s}'"

NEON_CONN_STR, NEON_HTTP_URL = get_neon_creds()


def resolve_facebook_user_name(sender_id):
    sender_id_str = str(sender_id).strip()
    if not sender_id_str:
        return "عميل فيسبوك"

    # 1. First check if DB already has a verified name for this sender_id
    try:
        sql = """
            SELECT sender_name FROM omnichannel_messages 
            WHERE sender_id = $1 AND sender_name NOT IN ('Messenger User', 'Admin', 'فريق 24Seven', 'ش', 'عميل فيسبوك', 'Facebook user', $1) 
            ORDER BY id DESC LIMIT 1
        """
        r = requests.post(
            NEON_HTTP_URL,
            headers={"Neon-Connection-String": NEON_CONN_STR},
            json={"query": sql, "params": [sender_id_str]},
            timeout=5
        )
        if r.status_code == 200:
            rows = r.json().get("rows", [])
            if rows and rows[0].get("sender_name"):
                return rows[0]["sender_name"]
    except Exception as e:
        print(f"Error checking DB for FB name: {e}")

    # 2. Call Facebook Graph API me/conversations
    fb_token = os.environ.get("FB_PAGE_TOKEN") or "EAAPDbwUyvY0BRN0VW4bIHPLRpeA7qHqK5TyFpNxJ8fuFcvVCshuBwZC52F59Q6oNH671nLZBbAiEsGSB55Vq0sHjyMIB4QNStzt6sFxRL7ImzttrnuFkHVTYWGZC0J2MgbBGfqo3dOi7Wo5QagQ7pY3vhZAztfKZBhNZCxGrVeGRIqz7pUkHHC2iM4ZA0mDje9oEXZCm"
    try:
        url = "https://graph.facebook.com/v18.0/me/conversations"
        params = {
            "access_token": fb_token,
            "user_id": sender_id_str,
            "fields": "participants"
        }
        r = requests.get(url, params=params, timeout=6)
        if r.status_code == 200:
            data = r.json()
            for conv in data.get('data', []):
                for p in conv.get('participants', {}).get('data', []):
                    if str(p.get('id')) == sender_id_str:
                        name = p.get('name', '').strip()
                        if name:
                            # Update DB so all messages for this sender have the real name
                            try:
                                upd_sql = """
                                    UPDATE omnichannel_messages 
                                    SET sender_name = $1 
                                    WHERE sender_id = $2 AND (sender_name IN ('Messenger User', 'عميل فيسبوك', 'Facebook user', $2) OR sender_name IS NULL)
                                """
                                requests.post(
                                    NEON_HTTP_URL,
                                    headers={"Neon-Connection-String": NEON_CONN_STR},
                                    json={"query": upd_sql, "params": [name, sender_id_str]},
                                    timeout=5
                                )
                            except Exception: pass
                            return name
    except Exception as e:
        print(f"Error querying Graph API for {sender_id}: {e}")

    # 3. Check reservations table (google_reservations) if PSID matches
    try:
        res_sql = """
            SELECT customer_name FROM google_reservations 
            WHERE (messenger_sender_id = $1 OR facebook_id = $1) AND customer_name IS NOT NULL AND customer_name != ''
            ORDER BY id DESC LIMIT 1
        """
        r2 = requests.post(
            NEON_HTTP_URL,
            headers={"Neon-Connection-String": NEON_CONN_STR},
            json={"query": res_sql, "params": [sender_id_str]},
            timeout=5
        )
        if r2.status_code == 200:
            rows = r2.json().get("rows", [])
            if rows and rows[0].get("customer_name"):
                return rows[0]["customer_name"]
    except Exception: pass

    return "عميل فيسبوك"

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

            if action == "resolve_facebook_user":
                sender_id = str(req.get("sender_id", "")).strip()
                if not sender_id:
                    self._respond(400, {"status": "error", "message": "sender_id required"})
                    return
                resolved_name = resolve_facebook_user_name(sender_id)
                self._respond(200, {"status": "ok", "name": resolved_name, "sender_id": sender_id})
                return

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
                
                is_trips_query = (table == "trips")
                if is_trips_query:
                    sql = """
                        SELECT 
                            t.*,
                            d.name AS driver_name, d.phone AS driver_phone,
                            c.brand AS car_brand, c.model AS car_model, c.plate_number AS car_plate_number, c.car_image_url AS car_image_url
                        FROM trips t
                        LEFT JOIN drivers d ON t.driver_id = d.id
                        LEFT JOIN cars c ON t.car_id = c.id
                        WHERE 1=1
                    """
                else:
                    if "(" in select_cols or ":" in select_cols:
                        select_cols = "*"
                    sql = f"SELECT {select_cols} FROM {table} WHERE 1=1"

                filters = req.get("filters", [])
                for f in filters:
                    op = f.get("op", "eq")
                    col = f.get("col")
                    # Prefix column with table alias if trips
                    db_col = f"t.{col}" if (is_trips_query and not col.startswith("t.")) else col
                    val = f.get("val")

                    if op == "eq":
                        sql += f" AND {db_col} = {sql_quote(val)}"
                    elif op == "neq":
                        sql += f" AND {db_col} != {sql_quote(val)}"
                    elif op == "gt":
                        sql += f" AND {db_col} > {sql_quote(val)}"
                    elif op == "gte":
                        sql += f" AND {db_col} >= {sql_quote(val)}"
                    elif op == "lt":
                        sql += f" AND {db_col} < {sql_quote(val)}"
                    elif op == "lte":
                        sql += f" AND {db_col} <= {sql_quote(val)}"
                    elif op == "like" or op == "ilike":
                        clean_v = str(val).strip().replace('%', '')
                        sql += f" AND {db_col} ILIKE {sql_quote(f'%{clean_v}%')}"
                    elif op == "in":
                        if isinstance(val, list) and len(val) > 0:
                            quoted_vals = [sql_quote(x) for x in val]
                            sql += f" AND {db_col} IN ({','.join(quoted_vals)})"
                    elif op == "is":
                        if val is None or val == "null":
                            sql += f" AND {db_col} IS NULL"
                        else:
                            sql += f" AND {db_col} IS NOT NULL"
                    elif op == "or":
                        or_parts = str(val).split(",")
                        sub_clauses = []
                        for op_part in or_parts:
                            if ".eq." in op_part:
                                c, v = op_part.split(".eq.", 1)
                                c_name = f"t.{c.strip()}" if (is_trips_query and not c.strip().startswith("t.")) else c.strip()
                                sub_clauses.append(f"{c_name} = {sql_quote(v.strip())}")
                            elif ".ilike." in op_part:
                                c, v = op_part.split(".ilike.", 1)
                                c_name = f"t.{c.strip()}" if (is_trips_query and not c.strip().startswith("t.")) else c.strip()
                                clean_v = v.strip().replace('%', '')
                                sub_clauses.append(f"{c_name} ILIKE {sql_quote(f'%{clean_v}%')}")
                        if sub_clauses:
                            sql += f" AND ({' OR '.join(sub_clauses)})"

                order = req.get("order")
                if order:
                    col = order.get("col", "id")
                    order_col = f"t.{col}" if (is_trips_query and not col.startswith("t.")) else col
                    asc = "ASC" if order.get("ascending", False) else "DESC"
                    sql += f" ORDER BY {order_col} {asc}"
                else:
                    sql += f" ORDER BY {'t.id' if is_trips_query else 'id'} DESC"

                limit = req.get("limit")
                if limit:
                    try:
                        sql += f" LIMIT {int(limit)}"
                    except:
                        pass

                r = requests.post(
                    NEON_HTTP_URL,
                    headers={"Neon-Connection-String": NEON_CONN_STR},
                    json={"query": sql},
                    timeout=12
                )
                rows = r.json().get("rows", []) if r.status_code == 200 else []
                
                # Format nested objects for trips
                if is_trips_query:
                    for row in rows:
                        d_name = row.pop("driver_name", None)
                        d_phone = row.pop("driver_phone", None)
                        if row.get("driver_id") or d_name:
                            row["drivers"] = {"name": d_name or "", "phone": d_phone or ""}
                        else:
                            row["drivers"] = None

                        c_brand = row.pop("car_brand", None)
                        c_model = row.pop("car_model", None)
                        c_plate = row.pop("car_plate_number", None)
                        c_img = row.pop("car_image_url", None)
                        if row.get("car_id") or c_brand:
                            row["cars"] = {
                                "brand": c_brand or "",
                                "model": c_model or "",
                                "plate_number": c_plate or "",
                                "car_image_url": c_img or ""
                            }
                        else:
                            row["cars"] = None

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
                    if r.status_code != 200:
                        err_msg = r.text
                        try:
                            err_msg = r.json().get("message", r.text)
                        except Exception:
                            pass
                        self._respond(400, {"status": "error", "message": err_msg})
                        return
                    inserted_rows.extend(r.json().get("rows", []))

                self._respond(200, {"status": "ok", "data": inserted_rows})

            elif action == "update":
                data_dict = req.get("data", {})
                eq_dict = req.get("eq", {})
                filters = req.get("filters", [])
                if not eq_dict and filters:
                    eq_dict = {f.get("col"): f.get("val") for f in filters if f.get("op") == "eq"}

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
                if r.status_code != 200:
                    err_msg = r.text
                    try:
                        err_msg = r.json().get("message", r.text)
                    except Exception:
                        pass
                    self._respond(400, {"status": "error", "message": err_msg})
                    return
                updated = r.json().get("rows", [])
                self._respond(200, {"status": "ok", "data": updated})

            elif action == "upsert":
                records = req.get("data", [])
                if isinstance(records, dict):
                    records = [records]
                if not records:
                    self._respond(200, {"status": "ok", "data": []})
                    return

                on_conflict_col = req.get("on_conflict", "id")
                inserted_rows = []
                for rec in records:
                    cols = list(rec.keys())
                    vals = list(rec.values())
                    placeholders = [f"${i+1}" for i in range(len(vals))]
                    update_set = [f"{c} = EXCLUDED.{c}" for c in cols if c != on_conflict_col]
                    if update_set:
                        sql = f"INSERT INTO {table} ({','.join(cols)}) VALUES ({','.join(placeholders)}) ON CONFLICT ({on_conflict_col}) DO UPDATE SET {', '.join(update_set)} RETURNING *;"
                    else:
                        sql = f"INSERT INTO {table} ({','.join(cols)}) VALUES ({','.join(placeholders)}) ON CONFLICT ({on_conflict_col}) DO NOTHING RETURNING *;"

                    r = requests.post(
                        NEON_HTTP_URL,
                        headers={"Neon-Connection-String": NEON_CONN_STR},
                        json={"query": sql, "params": vals},
                        timeout=12
                    )
                    if r.status_code != 200:
                        err_msg = r.text
                        try:
                            err_msg = r.json().get("message", r.text)
                        except Exception:
                            pass
                        self._respond(400, {"status": "error", "message": err_msg})
                        return
                    inserted_rows.extend(r.json().get("rows", []))

                self._respond(200, {"status": "ok", "data": inserted_rows})

            elif action == "delete":
                eq_dict = req.get("eq", {})
                filters = req.get("filters", [])
                if not eq_dict and filters:
                    eq_dict = {f.get("col"): f.get("val") for f in filters if f.get("op") == "eq"}
                if not eq_dict:
                    self._respond(400, {"status": "error", "message": "Missing eq filter for delete"})
                    return
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
                if r.status_code != 200:
                    err_msg = r.text
                    try:
                        err_msg = r.json().get("message", r.text)
                    except Exception:
                        pass
                    self._respond(400, {"status": "error", "message": err_msg})
                    return
                deleted = r.json().get("rows", [])
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
