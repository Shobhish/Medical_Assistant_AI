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

departments = [
    ("Cardiology", "Heart and blood vessel care"),
    ("Neurology", "Brain and nervous system care"),
    ("Orthopedics", "Bones, joints and muscles"),
    ("Pediatrics", "Healthcare for children"),
    ("General Medicine", "General checkups and common illnesses"),
]

# (full_name, department_name, qualification, available_days, available_time)
doctors = [
    ("Dr. Arun Menon", "Cardiology", "MD, DM Cardiology", "Mon, Wed, Fri", "10:00 AM - 1:00 PM"),
    ("Dr. Priya Nair", "Neurology", "MD, DM Neurology", "Tue, Thu", "2:00 PM - 5:00 PM"),
    ("Dr. Rahul Varma", "Orthopedics", "MS Orthopedics", "Mon, Tue, Thu", "9:00 AM - 12:00 PM"),
    ("Dr. Sneha Pillai", "Pediatrics", "MD Pediatrics", "Mon to Sat", "10:00 AM - 4:00 PM"),
    ("Dr. Anil Kumar", "General Medicine", "MBBS, MD", "Mon to Sat", "9:00 AM - 5:00 PM"),
]

try:
    with connection.cursor() as cursor:
        for name, description in departments:
            cursor.execute(
                """
                INSERT INTO departments (name, description)
                VALUES (%s, %s)
                ON CONFLICT (name) DO NOTHING;
                """,
                (name, description),
            )

        for full_name, dept_name, qualification, days, time in doctors:
            cursor.execute(
                """
                INSERT INTO doctors
                    (full_name, department_id, qualification, available_days, available_time)
                SELECT %s, id, %s, %s, %s
                FROM departments
                WHERE name = %s
                AND NOT EXISTS (SELECT 1 FROM doctors WHERE full_name = %s);
                """,
                (full_name, qualification, days, time, dept_name, full_name),
            )

    connection.commit()
    print("Sample data inserted successfully!")

except Exception as e:
    connection.rollback()
    print("Error:", e)

finally:
    connection.close()