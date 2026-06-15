import os

file_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "admin-crm.html"))
with open(file_path, "r", encoding="latin-1") as f:
    lines = f.readlines()

# Line 5496 (index 5495) contains the garbage bytes
# It should be: just part of JS between the isLocalAdminDuplicate and adminGroupedChats
# The garbage line is between the end of isLocalAdminDuplicate check and the next code block
# We need to figure out what should be there

# Looking at the structure:
# 5495: ...m.sender_id === msg.sender_id);
# 5496: ¯Ø©                  <-- garbage, should be removed
# 5497:                     adminGroupedChats[groupKey] = {

# The garbage line is at index 5495 (0-based)
garbage_line = lines[5495]
print(f"Garbage line content: {repr(garbage_line)}")

# Remove the garbage line
lines.pop(5495)

with open(file_path, "w", encoding="latin-1") as f:
    f.writelines(lines)

print("Removed garbage line successfully!")
