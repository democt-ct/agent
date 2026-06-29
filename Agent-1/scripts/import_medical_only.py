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

copy_pattern = re.compile(
    r'COPY public\.(\w+)\s*\(([^)]+)\)\s*FROM stdin;(.*?)(?=COPY public\.|ALTER TABLE|CREATE INDEX|$)',
    re.DOTALL
)

for m in copy_pattern.finditer(content):
    table = m.group(1)
    columns = [c.strip() for c in m.group(2).split(',')]
    data_section = m.group(3)

    if table != 'medical_records':
        continue

    end_idx = data_section.find('\\.')
    if end_idx == -1:
        data = data_section
    else:
        data = data_section[:end_idx]

    data = data.strip()

    col_str = ', '.join(columns)
    copy_sql = f'COPY public.{table} ({col_str}) FROM STDIN'

    try:
        cur.copy_expert(copy_sql, io.StringIO(data + '\n'))
        conn.commit()
        print(f'{table}: imported OK')
    except Exception as e:
        print(f'{table}: ERROR - {str(e)[:200]}')
        conn.rollback()

cur.execute('SELECT count(*) FROM medical_records')
print(f'medical_records count: {cur.fetchone()[0]}')

cur.close()
conn.close()
