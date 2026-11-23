from psycopg2 import errors

from database.booking import DAY_NAMES, parse_days, parse_time_window
from database.queries import get_connection, run_query

VALID_STATUSES = {"confirmed", "completed", "cancelled"}


# ---------- Bookings ----------
def list_appointments(date=None, doctor=None, status=None):
    """Return appointments, optionally filtered. Values are passed safely as parameters."""
    conditions = []
    params = []

    if date:
        conditions.append("a.appointment_date = %s")
        params.append(date)
    if doctor:
        conditions.append("d.full_name = %s")
        params.append(doctor)
    if status:
        conditions.append("a.status = %s")
        params.append(status)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    rows = run_query(
        f"""
        SELECT a.id, a.patient_name, a.patient_phone,
               d.full_name AS doctor,
               a.appointment_date, a.appointment_time, a.status
        FROM appointments a
        JOIN doctors d ON a.doctor_id = d.id
        {where}
        ORDER BY a.appointment_date, a.appointment_time
        LIMIT 500;
        """,
        params or None,
    )

    result = []
    for row in rows:
        item = dict(row)
        item["appointment_date"] = str(item["appointment_date"])
        item["appointment_time"] = str(item["appointment_time"])[:5]
        result.append(item)
    return result


def list_doctor_names():
    rows = run_query("SELECT full_name FROM doctors ORDER BY full_name;")
    return [r["full_name"] for r in rows]


def update_appointment_status(appointment_id, new_status):
    if new_status not in VALID_STATUSES:
        return {"ok": False, "error": "Invalid status."}

    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE appointments SET status = %s WHERE id = %s RETURNING id;",
                (new_status, appointment_id),
            )
            if cursor.fetchone() is None:
                connection.rollback()
                return {"ok": False, "error": "Appointment not found."}
        connection.commit()
        return {"ok": True, "id": appointment_id, "status": new_status}
    except errors.UniqueViolation:
        connection.rollback()
        return {
            "ok": False,
            "error": "That slot has been booked by someone else, so this cannot be reopened.",
        }
    except Exception:
        connection.rollback()
        return {"ok": False, "error": "Could not update the appointment."}
    finally:
        connection.close()


# ---------- Doctors ----------
def list_departments():
    return run_query("SELECT id, name FROM departments ORDER BY name;")


def list_doctors_full():
    return run_query(
        """
        SELECT d.id, d.full_name, d.department_id, dep.name AS department,
               d.qualification, d.available_days, d.available_time
        FROM doctors d
        JOIN departments dep ON d.department_id = dep.id
        ORDER BY dep.name, d.full_name;
        """
    )


def _validate_doctor(full_name, available_days, available_time):
    """Return an error message, or None if everything is fine."""
    name = full_name.strip()
    if not 3 <= len(name) <= 150:
        return "Doctor name must be 3 to 150 characters."

    try:
        days = parse_days(available_days)
        if not days or any(d not in DAY_NAMES for d in days):
            raise ValueError
    except Exception:
        return "Available days must look like 'Mon, Wed, Fri' or 'Mon to Sat'."

    try:
        start, end = parse_time_window(available_time)
        if start >= end:
            raise ValueError
    except Exception:
        return "Available time must look like '10:00 AM - 1:00 PM'."

    return None


def save_doctor(full_name, department_id, qualification, available_days,
                available_time, doctor_id=None):
    """Create a doctor (doctor_id=None) or update an existing one."""
    error = _validate_doctor(full_name, available_days, available_time)
    if error:
        return {"ok": False, "error": error}

    name = full_name.strip()

    # Booking finds doctors by name, so two doctors must not share one
    duplicate = run_query(
        "SELECT id FROM doctors WHERE LOWER(full_name) = LOWER(%s) AND id <> %s;",
        (name, doctor_id or 0),
    )
    if duplicate:
        return {"ok": False, "error": "A doctor with this name already exists."}

    values = (name, department_id, qualification.strip(),
              available_days.strip(), available_time.strip())

    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            if doctor_id is None:
                cursor.execute(
                    """
                    INSERT INTO doctors
                        (full_name, department_id, qualification, available_days, available_time)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id;
                    """,
                    values,
                )
            else:
                cursor.execute(
                    """
                    UPDATE doctors
                    SET full_name = %s, department_id = %s, qualification = %s,
                        available_days = %s, available_time = %s
                    WHERE id = %s
                    RETURNING id;
                    """,
                    values + (doctor_id,),
                )
            row = cursor.fetchone()
            if row is None:
                connection.rollback()
                return {"ok": False, "error": "Doctor not found."}
        connection.commit()
        return {"ok": True, "id": row[0]}
    except errors.ForeignKeyViolation:
        connection.rollback()
        return {"ok": False, "error": "Department not found."}
    except Exception:
        connection.rollback()
        return {"ok": False, "error": "Could not save the doctor."}
    finally:
        connection.close()


def delete_doctor(doctor_id):
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM doctors WHERE id = %s RETURNING id;", (doctor_id,))
            if cursor.fetchone() is None:
                connection.rollback()
                return {"ok": False, "error": "Doctor not found."}
        connection.commit()
        return {"ok": True}
    except errors.ForeignKeyViolation:
        connection.rollback()
        return {
            "ok": False,
            "error": "This doctor has appointments, so they cannot be deleted.",
        }
    except Exception:
        connection.rollback()
        return {"ok": False, "error": "Could not delete the doctor."}
    finally:
        connection.close()