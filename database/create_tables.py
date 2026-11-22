import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

connection = psycopg2.connect(
    host=os.getenv("DB_HOST"),
    port=os.getenv("DB_PORT"),
    dbname=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
)

try:
    with connection.cursor() as cursor:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS departments (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL UNIQUE,
                description TEXT
            );
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS doctors (
                id SERIAL PRIMARY KEY,
                full_name VARCHAR(150) NOT NULL,
                department_id INTEGER NOT NULL REFERENCES departments(id),
                qualification VARCHAR(150),
                available_days VARCHAR(100),
                available_time VARCHAR(100)
            );
        """)

    connection.commit()
    print("Tables created successfully!")

except Exception as e:
    connection.rollback()
    print("Error:", e)

finally:
    connection.close()