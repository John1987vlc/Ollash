#!/usr/bin/env python3
"""Clean the poker HTML file by removing thinking and extra content."""

import sys

with open('generated_projects/auto_agent_projects/poker_game/index.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Find DOCTYPE start
doctype_pos = content.find('<!DOCTYPE html>')
if doctype_pos == -1:
    print('ERROR: No DOCTYPE found')
    sys.exit(1)

# Find the LAST </html>
last_html_close = content.rfind('</html>')
if last_html_close == -1:
    print('ERROR: No </html> closing tag found')
    print('Searching for script tag end...')
    last_script_close = content.rfind('</script>')
    print(f'Last </script> at: {last_script_close}')
    last_body_close = content.rfind('</body>')
    print(f'Last </body> at: {last_body_close}')
    sys.exit(1)

# Extract clean HTML
clean_html = content[doctype_pos:last_html_close + len('</html>')]

print(f'Extracted: {len(clean_html)} chars of valid HTML')
print(f'Removed prefix: {doctype_pos} chars')
print(f'Removed suffix: {len(content) - last_html_close - len("</html>")} chars')

# Write back
with open('generated_projects/auto_agent_projects/poker_game/index.html', 'w', encoding='utf-8') as f:
    f.write(clean_html)

print('✓ File cleaned successfully')

# Verify
with open('generated_projects/auto_agent_projects/poker_game/index.html', 'r', encoding='utf-8') as f:
    final = f.read()
    
if final.startswith('<!DOCTYPE') and final.rstrip().endswith('</html>'):
    print('✓ Verification passed: proper HTML structure')
    print(f'Final size: {len(final)} bytes')
    # Show first 200 chars
    print(f'\nFirst 200 chars:\n{final[:200]}')
else:
    print('⚠ Verification failed')
    print(f'Starts with: {final[:50]}')
    print(f'Ends with: {final[-50:]}')
