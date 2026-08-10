with open('admin-crm.html', 'r', encoding='utf-8') as f:
    lines = f.readlines()

script_ends = []
for i, line in enumerate(lines):
    stripped = line.strip()
    if stripped == '</script>':
        script_ends.append(i+1)

print(f"Total script blocks: {len(script_ends)}")
print("Script end lines:")
for end_line in script_ends:
    start = max(0, end_line-6)
    print(f"\n--- Ends at line {end_line} ---")
    for j in range(start, min(end_line+1, len(lines))):
        safe_line = lines[j].rstrip().encode('ascii', errors='replace').decode('ascii')
        print(f"  {j+1}: {safe_line[:80]}")
