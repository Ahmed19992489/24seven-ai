with open('admin-crm.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Count script open/close tags
script_opens = content.count('<script')
script_closes = content.count('</script>')
print(f'Script opens: {script_opens}, closes: {script_closes}')

# Check for BOM
if content.startswith('\ufeff'):
    print('WARNING: File has UTF-8 BOM - removing...')
    content = content[1:]
else:
    print('No BOM - OK')

# Check page-section divs
page_sections = content.count('page-section')
print(f'page-section classes: {page_sections}')

# Check showPage function exists
if 'function showPage' in content:
    print('showPage function: FOUND OK')
else:
    print('showPage function: MISSING!')

# Check apiFetch exists  
if 'function apiFetch' in content:
    print('apiFetch function: FOUND OK')
else:
    print('apiFetch function: MISSING!')

# Check for the chat page element
if 'id="page-chat"' in content or "id='page-chat'" in content:
    print('page-chat div: FOUND OK')
else:
    print('page-chat div: MISSING OR DIFFERENT ID!')
    # Find omnichannel/inbox page
    import re
    inbox = re.findall(r'id="page-[^"]*"', content)
    print('Page section IDs found:', inbox[:15])
