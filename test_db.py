import psycopg2
from psycopg2.extras import RealDictCursor
import os
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    'host': os.environ.get('DB_HOST'),
    'port': int(os.environ.get('DB_PORT', 5432)),
    'database': os.environ.get('DB_NAME'),
    'user': os.environ.get('DB_USER'),
    'password': os.environ.get('DB_PASSWORD'),
    'sslmode': os.environ.get('DB_SSLMODE', 'require')  # default to 'require' if not set
}

try:
    connection = psycopg2.connect(**DB_CONFIG, cursor_factory=RealDictCursor)
    cursor = connection.cursor()

    # Test query
    cursor.execute("SELECT version();")
    result = cursor.fetchone()
    print("PostgreSQL Version:", result['version'])

    # Optional: check a table exists
    cursor.execute("SELECT * FROM riders LIMIT 1;")
    sample = cursor.fetchone()
    print("Sample rider row:", sample)

    cursor.close()
    connection.close()
    print("Database connection successful!")

except Exception as e:
    print("Database connection failed:", e)
