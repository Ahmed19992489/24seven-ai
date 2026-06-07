with open('admin-crm.html', 'r', encoding='utf-8') as f:
    lines = f.readlines()

with open('temp_admin_support_logic.txt', 'w', encoding='utf-8') as out:
    # Write lines 2750 to 2960 (0-indexed 2749 to 2959)
    for idx in range(2740, 2960):
        if idx < len(lines):
            out.write(f"Line {idx+1}: {lines[idx]}")
print("Extracted lines 2750 to 2960 to temp_admin_support_logic.txt")
