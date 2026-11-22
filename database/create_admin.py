import getpass

import bcrypt
from psycopg2 import errors

from database.queries import get_connection

username = input("Admin username: ").strip().lower()
if len(username) < 3:
    raise SystemExit("Username must be at least 3 characters.")

password = getpass.getpass("Password (min 10 characters): ")
if len(password) < 10:
    raise SystemExit("Password must be at least 10 characters.")
if password != getpass.getpass("Repeat password: "):
    raise SystemExit("Passwords do not match.")

password_hash = bcrypt.hashpw(password.encode("utf-8")[:72], bcrypt.gensalt()).decode("utf-8")

connection = get_connection()
try:
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO staff_users (username, password_hash, role) VALUES (%s, %s, 'admin');",
            (username, password_hash),
        )
    connection.commit()
    print(f"Admin '{username}' created.")
except errors.UniqueViolation:
    connection.rollback()
    print("That username already exists.")
finally:
    connection.close()