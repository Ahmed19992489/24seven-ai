import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

with open("admin-crm.html", "r", encoding="utf-8") as f:
    content = f.read()

print("File length:", len(content))

keywords = ["edit", "update", "تعديل", "تعديل الرحلة", "تعديل الحجز"]
for kw in keywords:
    matches = [m.start() for m in re.finditer(kw, content, re.IGNORECASE)]
    print(f"Keyword '{kw}' found {len(matches)} times")
    if matches:
        first_idx = matches[0]
        start_line = content[:first_idx].count("\n") + 1
        line_content = content.split("\n")[start_line - 1]
        print(f"  First match at line {start_line}: {line_content[:150]}")
