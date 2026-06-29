import sys, os, re, io
os.environ['PG_PORT'] = '5433'

import psycopg2

with open('migration/backups/patient_agent.sql', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('\\restrict pnle0J2c7SVUvA06TEqYXK8gRLDVQnMwC7EkJ6zP7KoIG5HjenxJxV4jWDWjPSM', '')
content = content.replace('\\unrestrict', '')

copy_blocks = re.split(r'(COPY public\.\w+\s*\([^)]+\)\s*FROM stdin;)', content)

# Just debug audit_log
i = 1
copy_stmt = copy_blocks[i].strip()
data_block = copy_blocks[i+1] if i+1 < len(copy_blocks) else ''

m = re.match(r'COPY public\.(\w+)\s*\(([^)]+)\)\s*FROM stdin;', copy_stmt)
table = m.group(1)
columns = [c.strip() for c in m.group(2).split(',')]

lines = data_block.split('\n')
data_lines = []
for line in lines:
    if line.strip() == '\\.':
        break
    data_lines.append(line)

data = '\n'.join(data_lines)

print(f'Table: {table}')
print(f'Columns: {len(columns)}')
print(f'Data lines: {len(data_lines)}')
print(f'Data length: {len(data)}')
print(f'Data repr (first 200): {repr(data[:200])}')
print(f'Data repr (last 100): {repr(data[-100:])}')
