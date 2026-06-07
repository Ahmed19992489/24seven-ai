import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

with open("vendor-dashboard.html", "r", encoding="utf-8") as f:
    content = f.read()

# Find occurrences of openAssignDriverModal
matches = [m.start() for m in re.finditer("openAssignDriverModal", content)]
for m in matches:
    start_line = content[:m].count("\n") + 1
    print(f"Line {start_line}: {content.split('\n')[start_line-1][:150]}")
