from database.queries import get_connection, run_query


def save_message(session_id, role, message):
    """Save one message. role is 'user' or 'assistant'."""
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO chat_history (session_id, role, message)
                VALUES (%s, %s, %s);
                """,
                (session_id, role, message),
            )
        connection.commit()
    finally:
        connection.close()


def get_recent_messages(session_id, limit=10):
    """Return the last few messages of a session, oldest first."""
    rows = run_query(
        """
        SELECT role, message
        FROM chat_history
        WHERE session_id = %s
        ORDER BY id DESC
        LIMIT %s;
        """,
        (session_id, limit),
    )
    return list(reversed(rows))