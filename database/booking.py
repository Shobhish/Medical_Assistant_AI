import json
import os
import re
import urllib.request
from datetime import date, datetime, timedelta

from psycopg2 import errors

from database.queries import get_connection, run_query

DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def notify_n8n(booking: dict) -> None:
    """Send the booking to n8n. A failure here must never break the booking."""
    url = os.getenv("N8N_WEBHOOK_URL")
    if not url:
        return
    try:
        request = urllib.request.Request(
            url,
            data=json.dumps(booking).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(request, timeout=3).close()
    except Exception as e:
        print(f"[n8n] notification failed: {e}")


def parse_days(text):
    """'Mon, Wed, Fri' -> ['Mon','Wed','Fri'];  'Mon to Sat' -> Mon..Sat"""
    text = text.strip()
    if " to " in text:
        start, end = [p.strip()[:3].title() for p in text.split(" to ")]
        return DAY_NAMES[DAY_NAMES.index(start): DAY_NAMES.index(end) + 1]
    return [p.strip()[:3].title() for p in text.split(",")]


def parse_time_window(text):
    """'10:00 AM - 1:00 PM' -> (time(10,0), time(13,0))"""
    start_text, end_text = [p.strip() for p in text.split(" - ")]
    start = datetime.strptime(start_text, "%I:%M %p").time()
    end = datetime.strptime(end_text, "%I:%M %p").time()
    return start, end


def book_appointment(
    patient_name: str,
    patient_phone: str,
    doctor_name: str,
    appointment_date: str,
    appointment_time: str,
) -> dict:
    """Book an appointment with a doctor. Call this ONLY after the patient has
    confirmed all the details.

    Args:
        patient_name: Full name of the patient.
        patient_phone: Patient's phone number (10 to 13 digits).
        doctor_name: Name of the doctor, for example "Dr. Arun Menon".
        appointment_date: Date in YYYY-MM-DD format.
        appointment_time: Time in 24-hour HH:MM format, on the hour or half hour.

    Returns:
        A dictionary with success True/False and either booking details or an error message.
    """
    name = patient_name.strip()
    if len(name) < 2:
        return {"success": False, "error": "Please provide the patient's full name."}

    digits = re.sub(r"\D", "", patient_phone)
    if not 10 <= len(digits) <= 13:
        return {"success": False, "error": "Please provide a valid phone number (10 to 13 digits)."}

    try:
        day = datetime.strptime(appointment_date, "%Y-%m-%d").date()
    except ValueError:
        return {"success": False, "error": "The date must be in YYYY-MM-DD format."}

    today = date.today()
    if day < today:
        return {"success": False, "error": "That date has already passed."}
    if day > today + timedelta(days=60):
        return {"success": False, "error": "Appointments can only be booked up to 60 days ahead."}

    try:
        slot = datetime.strptime(appointment_time, "%H:%M").time()
    except ValueError:
        return {"success": False, "error": "The time must be in HH:MM 24-hour format."}
    if slot.minute not in (0, 30):
        return {"success": False, "error": "Appointments are available on the hour or half hour only."}

    doctors = run_query(
        """
        SELECT id, full_name, available_days, available_time
        FROM doctors
        WHERE full_name ILIKE %s;
        """,
        (f"%{doctor_name.strip()}%",),
    )
    if not doctors:
        return {"success": False, "error": "No doctor found with that name."}
    if len(doctors) > 1:
        names = ", ".join(d["full_name"] for d in doctors)
        return {"success": False, "error": f"More than one doctor matches: {names}. Please be specific."}

    doctor = doctors[0]

    try:
        working_days = parse_days(doctor["available_days"])
        start, end = parse_time_window(doctor["available_time"])
    except Exception:
        return {"success": False, "error": "This doctor's schedule could not be read. Please contact reception."}

    weekday = DAY_NAMES[day.weekday()]
    if weekday not in working_days:
        return {
            "success": False,
            "error": f"{doctor['full_name']} is not available on {weekday}. "
                     f"Available days: {doctor['available_days']}.",
        }

    if not (start <= slot < end):
        return {
            "success": False,
            "error": f"{doctor['full_name']} is available between {doctor['available_time']}.",
        }

    if day == today and slot <= datetime.now().time():
        return {"success": False, "error": "That time has already passed today."}

    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO appointments
                    (patient_name, patient_phone, doctor_id,
                     appointment_date, appointment_time, status)
                VALUES (%s, %s, %s, %s, %s, 'confirmed')
                RETURNING id;
                """,
                (name, patient_phone.strip(), doctor["id"], day, slot),
            )
            appointment_id = cursor.fetchone()[0]
        connection.commit()
    except errors.UniqueViolation:
        connection.rollback()
        return {"success": False, "error": "That time slot is already booked. Please choose another time."}
    except Exception:
        connection.rollback()
        return {"success": False, "error": "Could not save the booking. Please try again."}
    finally:
        connection.close()

    result = {
        "success": True,
        "appointment_id": appointment_id,
        "patient_name": name,
        "doctor": doctor["full_name"],
        "date": day.strftime("%A, %d %B %Y"),
        "time": slot.strftime("%I:%M %p"),
    }
    # Tell n8n about the new booking (never breaks the booking if it fails)
    notify_n8n({**result, "patient_phone": patient_phone.strip()})
    return result