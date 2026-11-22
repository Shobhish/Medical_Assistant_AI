import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()


def get_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
    )


def run_query(sql, params=None):
    """Run a SELECT query and return a list of dictionaries."""
    connection = get_connection()
    try:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(sql, params)
            return cursor.fetchall()
    finally:
        connection.close()


def get_departments():
    return run_query("SELECT name, description FROM departments ORDER BY name;")


def get_doctors_by_department(department_name):
    return run_query(
        """
        SELECT d.full_name, dep.name AS department, d.qualification,
               d.available_days, d.available_time
        FROM doctors d
        JOIN departments dep ON d.department_id = dep.id
        WHERE dep.name ILIKE %s
        ORDER BY d.full_name;
        """,
        (f"%{department_name}%",),
    )


def get_doctor_by_name(doctor_name):
    return run_query(
        """
        SELECT d.full_name, dep.name AS department, d.qualification,
               d.available_days, d.available_time
        FROM doctors d
        JOIN departments dep ON d.department_id = dep.id
        WHERE d.full_name ILIKE %s;
        """,
        (f"%{doctor_name}%",),
    )


def get_all_doctors():
    return run_query(
        """
        SELECT d.full_name, dep.name AS department, d.qualification,
               d.available_days, d.available_time
        FROM doctors d
        JOIN departments dep ON d.department_id = dep.id
        ORDER BY dep.name, d.full_name;
        """
    )


def get_services():
    return run_query("SELECT name, description, price FROM services ORDER BY name;")


def search_faqs(keyword):
    return run_query(
        """
        SELECT question, answer, category
        FROM faqs
        WHERE question ILIKE %s OR answer ILIKE %s OR category ILIKE %s;
        """,
        (f"%{keyword}%", f"%{keyword}%", f"%{keyword}%"),
    )


def get_all_faqs():
    return run_query("SELECT question, answer FROM faqs;")