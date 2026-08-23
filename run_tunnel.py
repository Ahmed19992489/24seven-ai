import subprocess
import time
import sys
import os

sys.stdout.reconfigure(encoding='utf-8')

subdomain = "limo-24seven-official"
port = "3000"

print(f"==================================================")
print(f"🌐 24Seven Auto-Healing Tunnel Manager")
print(f"📌 Subdomain: https://{subdomain}.loca.lt")
print(f"🔌 Target Port: {port}")
print(f"==================================================\n")

while True:
    try:
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 🚀 Starting tunnel...")
        cmd = ["npx", "-y", "localtunnel", "--port", port, "--subdomain", subdomain, "--print-requests"]
        
        proc = subprocess.Popen(
            cmd,
            shell=True,
            stdout=sys.stdout,
            stderr=sys.stderr
        )
        
        proc.wait()
        print(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] ⚠️ Tunnel closed/disconnected. Reconnecting automatically in 3 seconds...\n")
        time.sleep(3)
    except KeyboardInterrupt:
        print("\nTunnel stopped by user.")
        break
    except Exception as e:
        print(f"\n[Error in tunnel manager]: {e}. Retrying in 3 seconds...")
        time.sleep(3)
