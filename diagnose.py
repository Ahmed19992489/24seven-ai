"""Diagnose the root cause of blank sections in admin-crm.html"""
import re

with open('admin-crm.html', 'r', encoding='utf-8') as f:
    content = f.read()
    lines = content.split('\n')

print("=" * 60)
print("DIAGNOSIS REPORT")
print("=" * 60)

# 1. Find all script block boundaries
script_starts = []
script_ends = []
for i, line in enumerate(lines):
    if '<script>' in line and 'src=' not in line:
        script_starts.append(i+1)
    if '</script>' in line and len(lines[i].strip()) < 20:
        script_ends.append(i+1)

print(f"\n1. Script blocks found: {len(script_starts)}")
for s, e in zip(script_starts, script_ends):
    print(f"   Script {s}-{e} ({e-s} lines)")

# 2. Find showPage definitions
print("\n2. showPage definitions:")
for i, line in enumerate(lines):
    if 'showPage' in line and ('function showPage' in line or 'window.showPage' in line):
        print(f"   Line {i+1}: {line.strip()[:80]}")

# 3. Find showPage('dashboard') call (initial call)
print("\n3. Initial showPage('dashboard') call:")
for i, line in enumerate(lines):
    if "showPage('dashboard')" in line and 'onclick' not in line and 'if' not in line:
        print(f"   Line {i+1}: {line.strip()[:80]}")

# 4. Find loader functions & which script block they're in
loaders = ['loadDashboard', 'loadOperations', 'setupOpsRealtime', 'loadCRM', 
           'loadFinance', 'loadFleetList', 'loadPartners', 'loadPricing',
           'loadAdminChats', 'loadRatings', 'loadCouponsPage', 'loadStaff',
           'loadMarketingStatus', 'loadTrainingReports', 'loadWhatsAppSettings',
           'resetWhatsappDetailsPanel', 'loadSniperBotPage']

print("\n4. Loader function definitions:")
for loader in loaders:
    found = False
    for i, line in enumerate(lines):
        if f'function {loader}' in line or f'async function {loader}' in line:
            # Find which script block
            block = '?'
            for j, (s, e) in enumerate(zip(script_starts, script_ends)):
                if s <= i+1 <= e:
                    block = j+1
                    break
            print(f"   Line {i+1} (Script {block}): {line.strip()[:60]}")
            found = True
            break
    if not found:
        print(f"   ⚠️  NOT FOUND: {loader}")

# 5. Check if functions are bound to window
print("\n5. window.* bindings for loaders:")
for loader in loaders:
    found = False
    for i, line in enumerate(lines):
        if f'window.{loader}' in line and '=' in line:
            print(f"   Line {i+1}: {line.strip()[:80]}")
            found = True
            break
    if not found:
        print(f"   ⚠️  No window.{loader} binding")

# 6. Check the main script's showPage function to see if it has typeof checks
print("\n6. Main showPage - does it have typeof checks?")
sp_idx = content.find('function showPage(pageId)')
if sp_idx > 0:
    sp_block = content[sp_idx:sp_idx+2000]
    has_typeof = 'typeof' in sp_block[:sp_block.find('}')]
    print(f"   Has typeof checks: {has_typeof}")
    # Find first line without typeof
    for call_fn in ['loadDashboard', 'loadOperations', 'setupOpsRealtime']:
        if call_fn in sp_block and f'typeof {call_fn}' not in sp_block[:sp_block.find(call_fn)+50]:
            print(f"   ⚠️  Direct call (no typeof): {call_fn}")

# 7. Check if DEBUG box is still in loadWhatsAppSettings
print("\n7. Debug artifacts remaining:")
if 'DEBUG' in content:
    for i, line in enumerate(lines):
        if 'DEBUG' in line:
            print(f"   Line {i+1}: {line.strip()[:80]}")

if 'alert(' in content and 'DEBUG' not in content:
    print("   No debug alerts remaining")

# 8. Check for the infinite reload cache buster
print("\n8. Cache buster / reload check:")
if 'location.replace' in content:
    for i, line in enumerate(lines):
        if 'location.replace' in line:
            print(f"   Line {i+1}: {line.strip()[:80]}")
else:
    print("   No location.replace found (good)")

print("\n" + "=" * 60)
print("DONE")
