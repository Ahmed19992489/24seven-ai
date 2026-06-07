with open('admin-crm.html', 'r', encoding='utf-8') as f:
    crm = f.read()
with open('moderator.html', 'r', encoding='utf-8') as f:
    mod = f.read()

with open('temp_support_search.txt', 'w', encoding='utf-8') as out:
    out.write("--- admin-crm.html ---\n")
    for idx, line in enumerate(crm.splitlines()):
        if 'support_chats' in line or 'support-chat' in line or 'supportChat' in line:
            out.write(f"Line {idx+1}: {line}\n")
            
    out.write("\n--- moderator.html ---\n")
    for idx, line in enumerate(mod.splitlines()):
        if 'support_chats' in line or 'support-chat' in line or 'supportChat' in line:
            out.write(f"Line {idx+1}: {line}\n")

print("Search complete. Saved to temp_support_search.txt")
