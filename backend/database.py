import os
import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import RealDictCursor

# Load environment variables from .env file
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

def get_db_connection():
    """
    Establish and return a connection to the PostgreSQL database.
    """
    try:
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    except Exception as e:
        print(f"Error connecting to database: {e}")
        return None

def execute_query(query, params=None, fetch=False):
    """
    Execute a SQL query. 
    If fetch is True, returns the results.
    """
    conn = get_db_connection()
    if conn is None:
        return None
    
    try:
        # Using RealDictCursor allows accessing columns by name like row['id']
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, params)
            if fetch:
                result = cur.fetchall()
            else:
                conn.commit()
                result = True
        return result
    except Exception as e:
        print(f"Query Error: {e}")
        conn.rollback()
        return None
    finally:
        conn.close()

if __name__ == "__main__":
    # Test connection
    print("Testing database connection...")
    connection = get_db_connection()
    if connection:
        print("✅ Connection successful!")
        connection.close()
    else:
        print("❌ Connection failed.")
