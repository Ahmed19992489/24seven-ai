import re
import subprocess
import os

with open('admin-crm.html', 'r', encoding='utf-8') as f:
    content = f.read()

scripts = re.findall(r'<script\b[^>]*>(.*?)</script>', content, re.DOTALL | re.IGNORECASE)

print(f"Total inline scripts: {len(scripts)}")

for i, script in enumerate(scripts):
    filename = f"scratch_script_{i}.js"
    with open(filename, "w", encoding="utf-8") as sf:
        sf.write(script)
    
    res = subprocess.run(["node", "--check", filename], capture_output=True, text=True)
    if res.returncode != 0:
        print(f"FAILED Script {i} has syntax error:")
        print(res.stderr)
    else:
        print(f"PASSED Script {i} is syntactically valid!")
    
    if os.path.exists(filename):
        os.remove(filename)
