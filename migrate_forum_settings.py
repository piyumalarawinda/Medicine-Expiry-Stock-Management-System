import sqlite3
import os

# Path to the database
db_path = os.path.join('database', 'pharmacy.db')

if not os.path.exists(db_path):
    print(f"Database not found at {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    # Check existing columns in settings table
    cursor.execute("PRAGMA table_info(settings)")
    columns = [column[1] for column in cursor.fetchall()]
    
    new_columns = [
        ('forum_enabled', 'BOOLEAN DEFAULT 1'),
        ('forum_general_talk', 'BOOLEAN DEFAULT 1'),
        ('forum_announcements', 'BOOLEAN DEFAULT 1'),
        ('forum_tips_tricks', 'BOOLEAN DEFAULT 1'),
        ('forum_bug_reports', 'BOOLEAN DEFAULT 1'),
        ('forum_feature_requests', 'BOOLEAN DEFAULT 1')
    ]
    
    for col_name, col_type in new_columns:
        if col_name not in columns:
            print(f"Adding column {col_name}...")
            cursor.execute(f"ALTER TABLE settings ADD COLUMN {col_name} {col_type}")
        else:
            print(f"Column {col_name} already exists.")
            
    conn.commit()
    print("Migration completed successfully!")
except Exception as e:
    print(f"Error during migration: {e}")
    conn.rollback()
finally:
    conn.close()
