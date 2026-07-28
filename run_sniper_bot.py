import os
import sys
import time
import sniper_agent

print("=" * 60)
print("🎯 24Seven Sniper Bot Service (Telegram Listener)")
print("   ✅ Running Telegram Polling Thread (Listening for /start & Alerts)")
print("   ℹ️  Note: WhatsApp group processing logs appear in 'webhook_server' window")
print("=" * 60 + "\n")

if __name__ == '__main__':
    try:
        sniper_agent.start_telegram_polling()
        print("[Sniper Bot] Telegram polling active. Press Ctrl+C to stop.\n")
        while True:
            time.sleep(10)
    except KeyboardInterrupt:
        print("\n[Sniper Bot] Stopped by user.")
    except Exception as e:
        print(f"\n[Sniper Bot Error]: {e}")
