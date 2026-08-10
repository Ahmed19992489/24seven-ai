import re

with open('admin-crm.html', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Search for any top-level Chart calls or other top-level executions outside functions
in_script = False
script_num = 0

for i, line in enumerate(lines):
    line_num = i + 1
    if '<script' in line.lower() and not 'src=' in line.lower():
        in_script = True
        script_num += 1
        continue
    if '</script>' in line.lower():
        in_script = False
        continue
    
    if in_script:
        # Check if top-level (not indented or only 8 spaces) and calling something risky
        stripped = line.strip()
        if stripped.startswith('new Chart(') or stripped.startswith('Chart('):
            print(f"Line {line_num}: Risky top-level Chart call: {stripped[:80]}")
        if stripped.startswith('showPage('):
            print(f"Line {line_num}: Top-level showPage call: {stripped[:80]}")
