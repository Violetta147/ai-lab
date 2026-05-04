import sqlite3
import json

db_path = r'C:\Users\violet\AppData\Roaming\Cursor\User\globalStorage\state.vscdb'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# List all tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
print("Tables:", tables)
for t in tables:
    cursor.execute(f'SELECT count(*) FROM "{t[0]}"')
    count = cursor.fetchone()[0]
    print(f'  {t[0]}: {count} rows')
    
    # Show schema
    cursor.execute(f"PRAGMA table_info('{t[0]}')")
    cols = cursor.fetchall()
    print(f'    Columns: {[c[1] for c in cols]}')

conn.close()
