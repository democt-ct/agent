import sys, os, re, io
os.environ['PG_PORT'] = '5433'

import psycopg2

conn = psycopg2.connect(
    host='localhost', port=5433, user='postgres', password='postgres',
    dbname='patient_agent'
)
cur = conn.cursor()

with open('migration/backups/patient_agent.sql', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('\\restrict pnle0J2c7SVUvA06TEqYXK8gRLDVQnMwC7EkJ6zP7KoIG5HjenxJxV4jWDWjPSM', '')
content = content.replace('\\unrestrict', '')

# Find medical_records COPY block
copy_blocks = re.split(r'(COPY public\.\w+\s*\([^)]+\)\s*FROM stdin;)', content)

for i in range(1, len(copy_blocks), 2):
    copy_stmt = copy_blocks[i].strip()
    data_block = copy_blocks[i+1] if i+1 < len(copy_blocks) else ''

    m = re.match(r'COPY public\.(\w+)\s*\(([^)]+)\)\s*FROM stdin;', copy_stmt)
    if not m:
        continue
    table = m.group(1)
    columns = [c.strip() for c in m.group(2).split(',')]

    if table != 'medical_records':
        continue

    lines = data_block.split('\n')
    data_lines = []
    for line in lines:
        if line.strip() == '\\.':
            break
        data_lines.append(line)

    print(f'Table: {table}')
    print(f'Columns: {len(columns)}')
    print(f'Data lines: {len(data_lines)}')

    # Debug: print first row's columns
    if data_lines:
        first_row = data_lines[0].lstrip('\n')
        parts = first_row.split('\t')
        print(f'First row has {len(parts)} tab-separated values')
        for j, (col, val) in enumerate(zip(columns, parts)):
            print(f'  {j}: {col} = {val[:50]}...' if len(val) > 50 else f'  {j}: {col} = {val}')

    break
