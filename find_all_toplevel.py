import re

with open('admin-crm.html', 'r', encoding='utf-8') as f:
    content = f.read()

scripts = re.findall(r'<script\b[^>]*>(.*?)</script>', content, re.DOTALL | re.IGNORECASE)

for idx, s in enumerate(scripts):
    print(f"=== SCRIPT {idx} ===")
    lines = s.split('\n')
    for line_no, line in enumerate(lines):
        # find top-level calls (0 or 4 spaces indent, calling a function)
        stripped = line.strip()
        if not stripped or stripped.startswith('//') or stripped.startswith('/*') or stripped.startswith('*'):
            continue
        if stripped.startswith('function ') or stripped.startswith('async function ') or stripped.startswith('class '):
            continue
        if stripped.startswith('var ') or stripped.startswith('let ') or stripped.startswith('const '):
            continue
        if stripped.startswith('window.') or stripped.startswith('document.'):
            print(f"  Line {line_no+1}: {stripped[:80]}")
        elif not line.startswith(' ') and not line.startswith('\t'):
            print(f"  Line {line_no+1} [top-level]: {stripped[:80]}")
