import os
import time
import traceback
import uuid
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel
from starlette.middleware.sessions import SessionMiddleware

from services.chatbot import ask
from database.staff_auth import verify_login
from database.staff_queries import (
    list_appointments,
    list_doctor_names,
    update_appointment_status,
    list_departments,
    list_doctors_full,
    save_doctor,
    delete_doctor,
)
from routes_services import router as services_router
from routes_public import router as public_router

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

# Extra routes kept in their own files
app.include_router(services_router)  # staff: manage services
app.include_router(public_router)    # public: data for the home page

# ---------- Login attempt limiter (simple, in memory) ----------
FAILED_LOGINS = {}
MAX_ATTEMPTS = 5
WINDOW_SECONDS = 300


def too_many_attempts(ip):
    now = time.time()
    recent = [t for t in FAILED_LOGINS.get(ip, []) if now - t < WINDOW_SECONDS]
    FAILED_LOGINS[ip] = recent
    return len(recent) >= MAX_ATTEMPTS


# ---------- Access checks (use these on every staff route) ----------
def require_staff(request: Request):
    username = request.session.get("staff_user")
    if not username:
        raise HTTPException(status_code=401, detail="Please log in.")
    return username


def require_admin(request: Request):
    """Like require_staff, but only for accounts with the admin role."""
    username = require_staff(request)
    if request.session.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required.")
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


class StatusUpdate(BaseModel):
    status: str


class DoctorIn(BaseModel):
    full_name: str
    department_id: int
    qualification: str = ""
    available_days: str
    available_time: str


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


# ---------- Staff pages ----------
@app.get("/staff")
def staff_dashboard(request: Request):
    if not request.session.get("staff_user"):
        return RedirectResponse(url="/staff/login", status_code=303)
    return FileResponse(BASE_DIR / "static" / "staff_dashboard.html")


@app.get("/staff/doctors")
def staff_doctors_page(request: Request):
    if not request.session.get("staff_user"):
        return RedirectResponse(url="/staff/login", status_code=303)
    if request.session.get("role") != "admin":
        return RedirectResponse(url="/staff", status_code=303)
    return FileResponse(BASE_DIR / "static" / "staff_doctors.html")


# ---------- Staff API: bookings (every route checks the login) ----------
@app.get("/staff/api/bookings")
def staff_bookings(
    request: Request,
    date: str | None = None,
    doctor: str | None = None,
    status: str | None = None,
):
    require_staff(request)

    if date:
        try:
            datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="Date must be YYYY-MM-DD.")

    return list_appointments(date or None, doctor or None, status or None)


@app.get("/staff/api/doctors")
def staff_doctors(request: Request):
    require_staff(request)
    return list_doctor_names()


@app.post("/staff/api/bookings/{appointment_id}/status")
def staff_update_status(appointment_id: int, data: StatusUpdate, request: Request):
    require_staff(request)
    result = update_appointment_status(appointment_id, data.status)
    if not result["ok"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


# ---------- Staff API: manage doctors (admin only) ----------
@app.get("/staff/api/manage/departments")
def manage_departments(request: Request):
    require_admin(request)
    return list_departments()


@app.get("/staff/api/manage/doctors")
def manage_doctors_list(request: Request):
    require_admin(request)
    return list_doctors_full()


@app.post("/staff/api/manage/doctors")
def manage_doctors_create(data: DoctorIn, request: Request):
    require_admin(request)
    result = save_doctor(
        data.full_name, data.department_id, data.qualification,
        data.available_days, data.available_time,
    )
    if not result["ok"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.put("/staff/api/manage/doctors/{doctor_id}")
def manage_doctors_update(doctor_id: int, data: DoctorIn, request: Request):
    require_admin(request)
    result = save_doctor(
        data.full_name, data.department_id, data.qualification,
        data.available_days, data.available_time, doctor_id=doctor_id,
    )
    if not result["ok"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.delete("/staff/api/manage/doctors/{doctor_id}")
def manage_doctors_delete(doctor_id: int, request: Request):
    require_admin(request)
    result = delete_doctor(doctor_id)
    if not result["ok"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return result