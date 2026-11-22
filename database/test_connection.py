import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

connection = None
try:
    connection = psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
    )
    print("Successfully connected to PostgreSQL!")

    with connection.cursor() as cursor:
        cursor.execute("SELECT current_database(), version();")
        db_name, version = cursor.fetchone()
        print("Database:", db_name)
        print("PostgreSQL version:", version)

except Exception as e:
    print("Connection failed:", e)

finally:
    if connection:
        connection.close()
        print("Database connection closed successfully.")