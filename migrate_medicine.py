import sqlite3
import os

def migrate():
    basedir = os.path.abspath(os.path.dirname(__file__))
    db_path = os.path.join(basedir, 'database', 'pharmacy.db')
    
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Check if is_active column exists
        cursor.execute("PRAGMA table_info(medicine)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'is_active' not in columns:
            print("Adding 'is_active' column to 'medicine' table...")
            cursor.execute("ALTER TABLE medicine ADD COLUMN is_active BOOLEAN DEFAULT 1")
            conn.commit()
            print("Migration successful: 'is_active' column added.")
        else:
            print("'is_active' column already exists in 'medicine' table.")
            
    except Exception as e:
        print(f"An error occurred during migration: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
