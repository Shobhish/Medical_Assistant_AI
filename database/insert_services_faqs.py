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

# (name, description, price)
services = [
    ("General Consultation", "Outpatient visit with a general physician", 500.00),
    ("Blood Test", "Complete blood count and basic panel", 400.00),
    ("X-Ray", "Digital X-ray imaging", 700.00),
    ("ECG", "Heart rhythm test", 350.00),
    ("Ultrasound", "Ultrasound scan", 1200.00),
]

# (question, answer, category)
faqs = [
    ("What are the visiting hours?",
     "Visiting hours are 4:00 PM to 7:00 PM every day.",
     "visiting"),
    ("Is the emergency department open 24 hours?",
     "Yes, our emergency department is open 24 hours a day, 7 days a week.",
     "emergency"),
    ("How can I book an appointment?",
     "You can book an appointment through this chat by giving your name, phone number, preferred doctor and time.",
     "appointments"),
    ("Do you accept health insurance?",
     "We accept most major insurance providers. Please carry your insurance card and ID when you visit.",
     "billing"),
    ("What documents should I bring for my first visit?",
     "Please bring a photo ID, any previous medical reports and your insurance card if you have one.",
     "general"),
]

try:
    with connection.cursor() as cursor:
        for name, description, price in services:
            cursor.execute(
                """
                INSERT INTO services (name, description, price)
                VALUES (%s, %s, %s)
                ON CONFLICT (name) DO NOTHING;
                """,
                (name, description, price),
            )

        for question, answer, category in faqs:
            cursor.execute(
                """
                INSERT INTO faqs (question, answer, category)
                VALUES (%s, %s, %s)
                ON CONFLICT (question) DO NOTHING;
                """,
                (question, answer, category),
            )

    connection.commit()
    print("Services and FAQs inserted successfully!")

except Exception as e:
    connection.rollback()
    print("Error:", e)

finally:
    connection.close()