import sys

with open('admin-crm.html', 'r', encoding='utf-8') as f:
    content = f.read()

replacements = [
    # sniper filters GET
    ("const res = await fetch(`${apiBase}/api/sniper/filters`);",
     "const res = await apiFetch(`${apiBase}/api/sniper/filters`);"),
    # sniper settings GET
    ("const res = await fetch(`${apiBase}/api/sniper/settings`);",
     "const res = await apiFetch(`${apiBase}/api/sniper/settings`);"),
    # sniper trips GET
    ("const res = await fetch(`${apiBase}/api/sniper/trips`);",
     "const res = await apiFetch(`${apiBase}/api/sniper/trips`);"),
    # marketing status (2 occurrences)
    ("const res = await fetch(`${apiBase}/api/marketing/status`);",
     "const res = await apiFetch(`${apiBase}/api/marketing/status`);"),
    # training reports
    ("const res = await fetch(`${apiBase}/api/training/reports`, {",
     "const res = await apiFetch(`${apiBase}/api/training/reports`, {"),
    # messenger broadcast
    ("const res = await fetch(`${apiBase}/api/messenger/broadcast`, {",
     "const res = await apiFetch(`${apiBase}/api/messenger/broadcast`, {"),
    # marketing broadcast
    ("const res = await fetch(`${apiBase}/api/marketing/broadcast`, {",
     "const res = await apiFetch(`${apiBase}/api/marketing/broadcast`, {"),
    # marketing stop
    ("const res = await fetch(`${apiBase}/api/marketing/stop`, {",
     "const res = await apiFetch(`${apiBase}/api/marketing/stop`, {"),
    # whatsapp instances load
    ("const res = await fetch(`${apiBase}/api/whatsapp/instances`);",
     "const res = await apiFetch(`${apiBase}/api/whatsapp/instances`);"),
    # whatsapp instances in selectWhatsappInstance
    ("const instRes = await fetch(`${apiBase}/api/whatsapp/instances`);",
     "const instRes = await apiFetch(`${apiBase}/api/whatsapp/instances`);"),
    # whatsapp instance status
    ("const statusRes = await fetch(`${apiBase}/api/whatsapp/instance/${id}/status`);",
     "const statusRes = await apiFetch(`${apiBase}/api/whatsapp/instance/${id}/status`);"),
    # whatsapp instance QR
    ("const res = await fetch(`${apiBase}/api/whatsapp/instance/${id}/qr`);",
     "const res = await apiFetch(`${apiBase}/api/whatsapp/instance/${id}/qr`);"),
    # whatsapp set-webhook
    ("const res = await fetch(`${apiBase}/api/whatsapp/instance/set-webhook`, {",
     "const res = await apiFetch(`${apiBase}/api/whatsapp/instance/set-webhook`, {"),
    # whatsapp delete instance
    ("const res = await fetch(`${apiBase}/api/whatsapp/instances/${id}`, {",
     "const res = await apiFetch(`${apiBase}/api/whatsapp/instances/${id}`, {"),
    # sniper filters POST
    ("const res = await fetch(`${apiBase}/api/sniper/filters`, {",
     "const res = await apiFetch(`${apiBase}/api/sniper/filters`, {"),
    # sniper filters DELETE
    ("const res = await fetch(`${apiBase}/api/sniper/filters/${id}`, {",
     "const res = await apiFetch(`${apiBase}/api/sniper/filters/${id}`, {"),
]

for old, new in replacements:
    count = content.count(old)
    content = content.replace(old, new)
    print(f'Replaced {count}x: {old[:70]}')

with open('admin-crm.html', 'w', encoding='utf-8', newline='') as f:
    f.write(content)

print('\nDone! File saved with UTF-8 encoding (CRLF preserved).')
