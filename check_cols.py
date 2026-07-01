from Python.constants import EditorCols
print('Total EditorCols:', len(list(EditorCols)))
print('Max value:', max(c.value for c in EditorCols))

with open('Python/ui/editor_tab.py','r') as f:
    content = f.read()
import re
match = re.search(r'headers = \[(.*?)\]', content, re.DOTALL)
if match:
    headers = re.findall(r'"([^"]+)"', match.group(1))
    print('Header count:', len(headers))
    print('Max col index:', len(headers)-1)
    if max(c.value for c in EditorCols) != len(headers)-1:
        print('MISMATCH: enum max != header count-1')
    else:
        print('Counts match OK')

# Check for removed column references
bad_refs = ['CLOUD_REMOTE_NAME', 'CLOUD_USER_PREFIX', 'CLOUD_REMOTE', 'CLOUD_USER', 
            'BACKUP_LOCAL_PREFIX', 'BACKUP_LOCAL_SAVE_PATH', 'BACKUP_ON_LAUNCH', 
            'BACKUP_ON_EXIT', 'BACKUP_MAX_BACKUPS']
for ref in bad_refs:
    if ref in content:
        print(f'FOUND BAD REF: {ref}')
    else:
        print(f'OK: {ref} not found')
