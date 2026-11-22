import os
import json
import time
import uuid
from datetime import date
from dotenv import load_dotenv
from google import genai
from google.genai import types

from database.queries import (
    get_departments,
    get_all_doctors,
    get_services,
    get_all_faqs,
)
from database.history import save_message, get_recent_messages
from database.booking import book_appointment

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# Quotas are counted per model, so we try several models in order
PRIMARY_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
BACKUP_MODELS = ["gemini-3.5-flash", "gemini-3.1-flash-lite", "gemini-3.5-flash-lite"]
MODELS = list(dict.fromkeys([PRIMARY_MODEL] + BACKUP_MODELS))

SYSTEM_PROMPT = """You are MediAssist AI, a friendly assistant for a hospital.

Rules:
1. Answer ONLY using the hospital data provided below. If the answer is not in the data, say you don't have that information and suggest contacting the hospital reception.
2. Never invent doctors, prices, timings or services.
3. You are not a doctor. Never diagnose, suggest medicines or give treatment advice. If someone describes symptoms, suggest they consult a suitable doctor from the list, and mention the relevant department.
4. If someone describes an emergency (chest pain, difficulty breathing, severe bleeding, unconsciousness), tell them to go to the emergency department immediately or call their local emergency number.
5. Keep replies short, clear and polite.

Appointment booking:
6. You can book appointments with the book_appointment tool.
7. Collect these five details from the patient: full name, phone number, doctor, date and time. Ask only for what is missing. Never make up any of them.
8. Doctors take appointments only within their available days and time, on the hour or half hour.
9. Before booking, repeat all the details and ask the patient to confirm. Call the tool only after they clearly say yes.
10. Convert dates like "tomorrow" or "next Monday" into YYYY-MM-DD using today's date given below, and times into 24-hour HH:MM.
11. Trust the tool result. If it returns an error, explain it simply and help the patient pick another day or time. Only say the appointment is booked when the tool returns success, and then give the appointment ID.
"""


def build_context():
    data = {
        "departments": get_departments(),
        "doctors": get_all_doctors(),
        "services": get_services(),
        "faqs": get_all_faqs(),
    }
    return json.dumps(data, default=str, indent=2)


def build_contents(session_id, question):
    """Earlier messages of this chat plus the new question."""
    contents = []
    for row in get_recent_messages(session_id, limit=10):
        role = "user" if row["role"] == "user" else "model"
        contents.append(
            types.Content(role=role, parts=[types.Part(text=row["message"])])
        )
    contents.append(types.Content(role="user", parts=[types.Part(text=question)]))
    return contents


def ask(question, session_id):
    today = date.today()
    system_instruction = (
        SYSTEM_PROMPT
        + f"\nToday's date is {today.strftime('%A')}, {today.isoformat()}.\n"
        + "\nHOSPITAL DATA:\n"
        + build_context()
    )
    config = types.GenerateContentConfig(
        system_instruction=system_instruction,
        tools=[book_appointment],
    )
    contents = build_contents(session_id, question)

    last_error = None
    for model in MODELS:
        for attempt in range(2):
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=contents,
                    config=config,
                )
                answer = response.text
                save_message(session_id, "user", question)
                save_message(session_id, "assistant", answer)
                return answer
            except Exception as e:
                last_error = e
                text = str(e)

                # Quota used up, or model not available: go to the next model
                if (
                    "429" in text
                    or "RESOURCE_EXHAUSTED" in text
                    or "404" in text
                    or "NOT_FOUND" in text
                ):
                    print(f"[chatbot] {model} skipped: {text[:70]}")
                    break

                # Server busy: wait a little and retry the same model
                if "503" in text or "UNAVAILABLE" in text:
                    time.sleep(2 * (attempt + 1))
                    continue

                # Anything else is a real bug: show it
                raise

    raise last_error


if __name__ == "__main__":
    session_id = str(uuid.uuid4())
    print(f"MediAssist AI (type 'exit' to quit) | session: {session_id}")
    while True:
        user_input = input("\nYou: ").strip()
        if user_input.lower() == "exit":
            break
        if not user_input:
            continue
        try:
            print("Assistant:", ask(user_input, session_id))
        except Exception as e:
            print("Error:", e)