import bcrypt

from database.queries import run_query

# Used so a wrong username takes about as long as a wrong password
DUMMY_HASH = bcrypt.hashpw(b"dummy-password", bcrypt.gensalt())


def verify_login(username, password):
    """Return {'username', 'role'} if the login is correct, otherwise None."""
    rows = run_query(
        "SELECT username, password_hash, role FROM staff_users WHERE username = %s;",
        (username.lower(),),
    )
    password_bytes = password.encode("utf-8")[:72]  # bcrypt reads at most 72 bytes

    if not rows:
        bcrypt.checkpw(password_bytes, DUMMY_HASH)
        return None

    user = rows[0]
    if bcrypt.checkpw(password_bytes, user["password_hash"].encode("utf-8")):
        return {"username": user["username"], "role": user["role"]}
    return None