import os
import sys
import time
import requests
import json
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8')

FB_PAGE_TOKEN = os.getenv("FB_PAGE_TOKEN") or "EAAPDbwUyvY0BRN0VW4bIHPLRpeA7qHqK5TyFpNxJ8fuFcvVCshuBwZC52F59Q6oNH671nLZBbAiEsGSB55Vq0sHjyMIB4QNStzt6sFxRL7ImzttrnuFkHVTYWGZC0J2MgbBGfqo3dOi7Wo5QagQ7pY3vhZAztfKZBhNZCxGrVeGRIqz7pUkHHC2iM4ZA0mDje9oEXZCm"
PAGE_ID = "101903822442322"
NEON_CONN_STR = os.getenv("DATABASE_URL") or "postgresql://neondb_owner:npg_WFZmc7X1YEMQ@ep-falling-glade-a5v7q460-pooler.us-east-2.aws.neon.tech/neondb?sslmode=require"
NEON_HTTP_URL = "https://ep-falling-glade-a5v7q460-pooler.us-east-2.aws.neon.tech/sql"

def insert_to_db(db_data):
    sql = """
    INSERT INTO omnichannel_messages (channel, sender_id, sender_name, message_text, is_from_admin, read_by_admin, created_at)
    VALUES ($1, $2, $3, $4, $5, $6, $7)
    RETURNING id;
    """
    params = [
        db_data["channel"],
        db_data["sender_id"],
        db_data["sender_name"],
        db_data["message_text"],
        db_data["is_from_admin"],
        db_data["read_by_admin"],
        db_data["created_at"]
    ]
    headers = {"Neon-Connection-String": NEON_CONN_STR}
    r = requests.post(NEON_HTTP_URL, headers=headers, json={"query": sql, "params": params}, timeout=10)
    return r.status_code == 200

def sync_facebook_messages():
    if not FB_PAGE_TOKEN:
        print("❌ No FB_PAGE_TOKEN configured.")
        return

    url = "https://graph.facebook.com/v19.0/me/conversations"
    params = {
        "access_token": FB_PAGE_TOKEN,
        "fields": "id,updated_time,participants,messages.limit(15){id,message,from,created_time,attachments}",
        "limit": 25
    }

    try:
        r = requests.get(url, params=params, timeout=20)
        if r.status_code != 200:
            print(f"❌ Error fetching conversations from Meta: {r.status_code} - {r.text[:200]}")
            return

        data = r.json()
        conversations = data.get("data", [])
        print(f"📥 Fetched {len(conversations)} conversations from Meta.")

        # Load existing messages to avoid duplicates
        headers = {"Neon-Connection-String": NEON_CONN_STR}
        existing_res = requests.post(NEON_HTTP_URL, headers=headers, json={
            "query": "SELECT sender_id, message_text, is_from_admin FROM omnichannel_messages WHERE channel = 'messenger' ORDER BY id DESC LIMIT 500;"
        }, timeout=10)
        existing_set = set()
        if existing_res.status_code == 200:
            for row in existing_res.json().get("rows", []):
                existing_set.add((row.get("sender_id"), row.get("message_text"), row.get("is_from_admin")))

        total_inserted = 0

        for conv in conversations:
            participants = conv.get("participants", {}).get("data", [])
            client = next((p for p in participants if str(p.get("id")) != PAGE_ID), None)

            if not client:
                continue

            client_id = str(client.get("id"))
            client_name = client.get("name") or "عميل فيسبوك"

            messages = conv.get("messages", {}).get("data", [])
            messages.reverse()  # Oldest to newest

            for msg in messages:
                msg_text = msg.get("message")
                attachments = msg.get("attachments", {}).get("data", [])

                if not msg_text and attachments:
                    msg_text = "[مرفق / صورة]"
                elif not msg_text:
                    continue

                from_id = str(msg.get("from", {}).get("id", ""))
                is_admin = (from_id == PAGE_ID)
                created_time = msg.get("created_time")

                if (client_id, msg_text, is_admin) in existing_set:
                    continue

                db_data = {
                    "channel": "messenger",
                    "sender_id": client_id,
                    "sender_name": client_name if not is_admin else "فريق 24Seven",
                    "message_text": msg_text,
                    "is_from_admin": is_admin,
                    "read_by_admin": is_admin,
                    "created_at": created_time or datetime.utcnow().isoformat()
                }

                try:
                    if insert_to_db(db_data):
                        total_inserted += 1
                        existing_set.add((client_id, msg_text, is_admin))
                except Exception as ex:
                    print(f"Insert error: {ex}")

        if total_inserted > 0:
            print(f"✅ Sync complete! Inserted {total_inserted} new Meta messages with verified customer names into Neon.")
        else:
            print("✨ Meta sync check complete - all messages are up to date.")

    except Exception as e:
        print(f"❌ Exception in sync_facebook_messages: {e}")

if __name__ == "__main__":
    is_loop = "--loop" in sys.argv
    if is_loop:
        print("🔄 Meta Continuous Sync Daemon active (polling every 30s)...")
        while True:
            try:
                sync_facebook_messages()
            except Exception as e:
                print(f"Loop error: {e}")
            time.sleep(30)
    else:
        sync_facebook_messages()
