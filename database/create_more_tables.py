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
            CREATE TABLE IF NOT EXISTS services (
                id SERIAL PRIMARY KEY,
                name VARCHAR(150) NOT NULL UNIQUE,
                description TEXT,
                price NUMERIC(10, 2)
            );
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS faqs (
                id SERIAL PRIMARY KEY,
                question TEXT NOT NULL UNIQUE,
                answer TEXT NOT NULL,
                category VARCHAR(100)
            );
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS appointments (
                id SERIAL PRIMARY KEY,
                patient_name VARCHAR(150) NOT NULL,
                patient_phone VARCHAR(20) NOT NULL,
                doctor_id INTEGER NOT NULL REFERENCES doctors(id),
                appointment_date DATE NOT NULL,
                appointment_time TIME NOT NULL,
                status VARCHAR(20) NOT NULL DEFAULT 'pending',
                created_at TIMESTAMP NOT NULL DEFAULT NOW()
            );
        """)

        # Prevents two active bookings for the same doctor at the same time
        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS unique_active_slot
            ON appointments (doctor_id, appointment_date, appointment_time)
            WHERE status <> 'cancelled';
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chat_history (
                id SERIAL PRIMARY KEY,
                session_id VARCHAR(100) NOT NULL,
                role VARCHAR(20) NOT NULL,
                message TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT NOW()
            );
        """)

    connection.commit()
    print("All tables created successfully!")

except Exception as e:
    connection.rollback()
    print("Error:", e)

finally:
    connection.close()