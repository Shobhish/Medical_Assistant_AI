from decimal import Decimal, InvalidOperation

from psycopg2 import errors

from database.queries import get_connection, run_query


def _write(sql, params):
    """Run an INSERT, UPDATE or DELETE that ends with RETURNING id."""
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(sql, params)
            row = cursor.fetchone()
            if row is None:
                connection.rollback()
                return {"ok": False, "error": "Service not found."}
        connection.commit()
        return {"ok": True, "id": row[0]}
    except errors.UniqueViolation:
        connection.rollback()
        return {"ok": False, "error": "A service with this name already exists."}
    except Exception:
        connection.rollback()
        return {"ok": False, "error": "Could not save. Please try again."}
    finally:
        connection.close()


def list_services():
    rows = run_query("SELECT id, name, description, price FROM services ORDER BY name;")
    result = []
    for row in rows:
        item = dict(row)
        item["price"] = float(item["price"]) if item["price"] is not None else None
        result.append(item)
    return result


def save_service(name, description, price, service_id=None):
    name = name.strip()
    if not 2 <= len(name) <= 150:
        return {"ok": False, "error": "Service name must be 2 to 150 characters."}

    try:
        amount = Decimal(str(price)).quantize(Decimal("0.01"))
        if not amount.is_finite() or amount < 0 or amount > Decimal("1000000"):
            raise InvalidOperation
    except (InvalidOperation, ValueError):
        return {"ok": False, "error": "Price must be a number between 0 and 1,000,000."}

    if service_id is None:
        return _write(
            "INSERT INTO services (name, description, price) VALUES (%s, %s, %s) RETURNING id;",
            (name, description.strip(), amount),
        )
    return _write(
        "UPDATE services SET name = %s, description = %s, price = %s WHERE id = %s RETURNING id;",
        (name, description.strip(), amount, service_id),
    )


def delete_service(service_id):
    return _write("DELETE FROM services WHERE id = %s RETURNING id;", (service_id,))