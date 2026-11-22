import traceback
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from services.chatbot import ask

BASE_DIR = Path(__file__).parent

app = FastAPI(title="MediAssist AI")


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None


class ChatResponse(BaseModel):
    reply: str
    session_id: str


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
        # Print the real error in the terminal so we can see what went wrong
        traceback.print_exc()
        text = str(e)
        if "503" in text or "UNAVAILABLE" in text or "429" in text:
            raise HTTPException(
                status_code=503,
                detail="The assistant is busy right now. Please try again in a moment.",
            )
        raise HTTPException(
            status_code=500,
            detail="Something went wrong on our side. Please try again.",
        )

    return ChatResponse(reply=reply, session_id=session_id)