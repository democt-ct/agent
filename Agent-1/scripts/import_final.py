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

# Find all COPY blocks
copy_pattern = re.compile(
    r'COPY public\.(\w+)\s*\(([^)]+)\)\s*FROM stdin;(.*?)(?=COPY public\.|ALTER TABLE|CREATE INDEX|$)',
    re.DOTALL
)

for m in copy_pattern.finditer(content):
    table = m.group(1)
    columns = [c.strip() for c in m.group(2).split(',')]
    data_section = m.group(3)

    # Extract data between start and \.
    end_idx = data_section.find('\\.')
    if end_idx == -1:
        data = data_section
    else:
        data = data_section[:end_idx]

    data = data.strip()

    if not data:
        print(f'{table}: 0 rows (empty)')
        continue

    col_str = ', '.join(columns)
    copy_sql = f'COPY public.{table} ({col_str}) FROM STDIN'

    try:
        cur.copy_expert(copy_sql, io.StringIO(data + '\n'))
        print(f'{table}: imported OK')
    except Exception as e:
        print(f'{table}: ERROR - {str(e)[:150]}')
        conn.rollback()
        conn = psycopg2.connect(host='localhost', port=5433, user='postgres', password='postgres', dbname='patient_agent')
        cur = conn.cursor()

conn.commit()
print('\n--- Row counts ---')

cur.execute("""
    SELECT 'audit_log' as tbl, count(*) from audit_log UNION ALL
    SELECT 'patients', count(*) from patients UNION ALL
    SELECT 'medical_records', count(*) from medical_records UNION ALL
    SELECT 'visit_records', count(*) from visit_records UNION ALL
    SELECT 'memory_knowledge_chunks', count(*) from memory_knowledge_chunks UNION ALL
    SELECT 'memory_user_profiles', count(*) from memory_user_profiles UNION ALL
    SELECT 'memory_business_profiles', count(*) from memory_business_profiles UNION ALL
    SELECT 'memory_conversation_profiles', count(*) from memory_conversation_profiles UNION ALL
    SELECT 'memory_key_events_v2', count(*) from memory_key_events_v2 UNION ALL
    SELECT 'memory_preferences', count(*) from memory_preferences UNION ALL
    SELECT 'memory_session_buffer_messages', count(*) from memory_session_buffer_messages UNION ALL
    SELECT 'memory_conversation_messages', count(*) from memory_conversation_messages
    ORDER BY tbl
""")
for row in cur.fetchall():
    print(f'{row[0]}: {row[1]}')

cur.close()
conn.close()
