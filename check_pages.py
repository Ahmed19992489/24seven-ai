with open('admin-crm.html', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if '<main' in line or '</main>' in line:
        print(f"Line {i+1}: {line.strip()[:80]}")
    if 'id="page-' in line:
        print(f"Line {i+1}: {line.strip()[:80]}")
