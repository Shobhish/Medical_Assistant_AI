import os
import time
import traceback
import uuid
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel
from starlette.middleware.sessions import SessionMiddleware

from services.chatbot import ask
from database.staff_auth import verify_login

load_dotenv()

BASE_DIR = Path(__file__).parent

SESSION_SECRET = os.getenv("SESSION_SECRET")
if not SESSION_SECRET:
    raise RuntimeError("SESSION_SECRET is missing in .env")

app = FastAPI(title="MediAssist AI")

# Signed cookie that remembers who is logged in.
# When you deploy with HTTPS, change https_only to True.
app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    max_age=60 * 60 * 8,  # 8 hours
    same_site="lax",
    https_only=False,
)

# ---------- Login attempt limiter (simple, in memory) ----------
FAILED_LOGINS = {}
MAX_ATTEMPTS = 5
WINDOW_SECONDS = 300


def too_many_attempts(ip):
    now = time.time()
    recent = [t for t in FAILED_LOGINS.get(ip, []) if now - t < WINDOW_SECONDS]
    FAILED_LOGINS[ip] = recent
    return len(recent) >= MAX_ATTEMPTS


def require_staff(request: Request):
    """Use this on every staff-only route."""
    username = request.session.get("staff_user")
    if not username:
        raise HTTPException(status_code=401, detail="Please log in.")
    return username


# ---------- Models ----------
class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None


class ChatResponse(BaseModel):
    reply: str
    session_id: str


class LoginRequest(BaseModel):
    username: str
    password: str


# ---------- Public pages and chat ----------
@app.get("/")
def home():
    return FileResponse(BASE_DIR / "static" / "index.html")


@app.get("/health")
def health_check():
    return {"status": "MediAssist AI is running"}


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    message = request.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    session_id = request.session_id or str(uuid.uuid4())

    try:
        reply = ask(message, session_id)
    except Exception as e:
        traceback.print_exc()
        text = str(e)
        if "429" in text or "RESOURCE_EXHAUSTED" in text:
            raise HTTPException(
                status_code=429,
                detail="The assistant has reached its usage limit for now. Please try again later.",
            )
        if "503" in text or "UNAVAILABLE" in text:
            raise HTTPException(
                status_code=503,
                detail="The assistant is busy right now. Please try again in a moment.",
            )
        raise HTTPException(
            status_code=500,
            detail="Something went wrong on our side. Please try again.",
        )

    return ChatResponse(reply=reply, session_id=session_id)


# ---------- Staff login ----------
@app.get("/staff/login")
def staff_login_page():
    return FileResponse(BASE_DIR / "static" / "staff_login.html")


@app.post("/staff/login")
def staff_login(data: LoginRequest, request: Request):
    ip = request.client.host if request.client else "unknown"

    if too_many_attempts(ip):
        raise HTTPException(
            status_code=429,
            detail="Too many failed attempts. Please wait a few minutes.",
        )

    user = verify_login(data.username.strip(), data.password)
    if not user:
        FAILED_LOGINS.setdefault(ip, []).append(time.time())
        raise HTTPException(status_code=401, detail="Incorrect username or password.")

    FAILED_LOGINS.pop(ip, None)
    request.session.clear()
    request.session["staff_user"] = user["username"]
    request.session["role"] = user["role"]
    return {"username": user["username"], "role": user["role"]}


@app.post("/staff/logout")
def staff_logout(request: Request):
    request.session.clear()
    return {"ok": True}


@app.get("/staff/me")
def staff_me(request: Request):
    username = require_staff(request)
    return {"username": username, "role": request.session.get("role", "staff")}


@app.get("/staff")
def staff_dashboard(request: Request):
    if not request.session.get("staff_user"):
        return RedirectResponse(url="/staff/login", status_code=303)
    return FileResponse(BASE_DIR / "static" / "staff_dashboard.html")