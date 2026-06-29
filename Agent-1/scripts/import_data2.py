import sys, os, re, io
os.environ['PG_PORT'] = '5433'

with open('migration/backups/patient_agent.sql', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('\\restrict pnle0J2c7SVUvA06TEqYXK8gRLDVQnMwC7EkJ6zP7KoIG5HjenxJxV4jWDWjPSM', '')
content = content.replace('\\unrestrict', '')

copy_blocks = re.split(r'(COPY public\.\w+\s*\([^)]+\)\s*FROM stdin;)', content)

for i in range(1, len(copy_blocks), 2):
    copy_stmt = copy_blocks[i].strip()
    data_block = copy_blocks[i+1] if i+1 < len(copy_blocks) else ''

    m = re.match(r'COPY public\.(\w+)\s*\(([^)]+)\)\s*FROM stdin;', copy_stmt)
    if not m:
        continue
    table = m.group(1)
    columns = [c.strip() for c in m.group(2).split(',')]

    # Find data between COPY and \.
    # The \. is on its own line
    lines = data_block.split('\n')
    data_lines = []
    for line in lines:
        if line.strip() == '\\.':
            break
        data_lines.append(line)

    data = '\n'.join(data_lines)

    print(f'\n=== {table} ===')
    print(f'Columns ({len(columns)}): {columns[:3]}...')
    print(f'Data lines: {len(data_lines)}')
    if data_lines:
        print(f'First line preview: {data_lines[0][:100]}...')
