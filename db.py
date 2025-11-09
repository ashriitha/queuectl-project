

import sqlite3
import os


DB_FILE = "queue.db"

def get_db_connection():
    """
    Creates a new database connection.
    This connection is what we use to send SQL commands.
    """
  
    conn = sqlite3.connect(DB_FILE)
    
  
    conn.row_factory = sqlite3.Row
    return conn

def initialize_database():
 
    
  
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS jobs (
        id TEXT PRIMARY KEY,
        command TEXT NOT NULL,
        state TEXT NOT NULL DEFAULT 'pending',
        attempts INTEGER NOT NULL DEFAULT 0,
        
        -- Timestamps for logging and for the 'run_at' logic
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        
        -- This is the key for exponential backoff!
        -- A worker can only pick up jobs where run_at <= now()
        run_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        
        -- Bonus: We'll add these now to make logging easier later
        output_log TEXT,
        error_log TEXT
    );
    """
    

    create_trigger_sql = """
    CREATE TRIGGER IF NOT EXISTS update_jobs_updated_at
    AFTER UPDATE ON jobs
    FOR EACH ROW
    BEGIN
        UPDATE jobs SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
    END;
    """

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        print("Creating 'jobs' table if it doesn't exist...")
        cursor.execute(create_table_sql)
        
        print("Creating 'updated_at' trigger...")
        cursor.execute(create_trigger_sql)
        
        conn.commit()
        conn.close()
        
        print(f"Database '{DB_FILE}' initialized successfully.")
        
    except sqlite3.Error as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    if not os.path.exists(DB_FILE):
        initialize_database()
    else:
        print(f"Database file '{DB_FILE}' already exists.")