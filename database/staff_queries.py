from psycopg2 import errors

from database.queries import get_connection, run_query

VALID_STATUSES = {"confirmed", "completed", "cancelled"}


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