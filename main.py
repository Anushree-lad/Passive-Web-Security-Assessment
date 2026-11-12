"""
Assistant Hub — FastAPI skeleton
--------------------------------
A local multi-assistant dashboard. Each entry in SECTIONS becomes a page,
reachable at /assistant/<key>, sharing one sidebar and one template.

Run it:
    pip install -r requirements.txt
    uvicorn main:app --reload
Then open http://127.0.0.1:8000
"""

import json
import hashlib
import secrets
import requests
from datetime import datetime
from pathlib import Path
from fastapi import FastAPI, Request, Form
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse

app = FastAPI(title="Assistant Hub")

# ---------------------------------------------------------------------------
# User accounts — stored locally in users.json as:
#   { "someone@email.com": {"salt": "...", "hash": "..."} }
# Passwords are never stored in plain text, only a salted hash.
# Anyone can sign up at /signup; logging in just needs their own email + password.
# ---------------------------------------------------------------------------
USERS_PATH = Path(__file__).parent / "users.json"
AUTH_COOKIE = "hub_user"


def load_users() -> dict:
    if not USERS_PATH.exists():
        return {}
    try:
        return json.loads(USERS_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_users(data: dict) -> None:
    USERS_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def hash_password(password: str, salt: str) -> str:
    return hashlib.sha256((salt + password).encode("utf-8")).hexdigest()


def create_user(email: str, password: str) -> None:
    users = load_users()
    salt = secrets.token_hex(8)
    users[email] = {"salt": salt, "hash": hash_password(password, salt)}
    save_users(users)


def verify_user(email: str, password: str) -> bool:
    users = load_users()
    record = users.get(email)
    if not record:
        return False
    return hash_password(password, record["salt"]) == record["hash"]


def current_user(request: Request) -> str | None:
    email = request.cookies.get(AUTH_COOKIE)
    if email and email in load_users():
        return email
    return None


def is_authed(request: Request) -> bool:
    return current_user(request) is not None

# ---------------------------------------------------------------------------
# Chat history — stored as a simple JSON file: { "<section_key>": [ {role, text, time}, ... ] }
# ---------------------------------------------------------------------------
HISTORY_PATH = Path(__file__).parent / "history.json"


def load_history() -> dict:
    if not HISTORY_PATH.exists():
        return {}
    try:
        return json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_history(data: dict) -> None:
    HISTORY_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def append_message(key: str, role: str, text: str) -> None:
    data = load_history()
    data.setdefault(key, []).append(
        {"role": role, "text": text, "time": datetime.now().strftime("%Y-%m-%d %H:%M")}
    )
    save_history(data)

# ---------------------------------------------------------------------------
# Ollama config — make sure `ollama serve` / the Ollama app is running, and
# that you've pulled this model (`ollama pull llama3.2`).
# ---------------------------------------------------------------------------
OLLAMA_URL = "http://localhost:11434/api/chat"
OLLAMA_MODEL = "llama3"

# One system prompt per section — this is what makes each page feel like a
# different assistant even though they all hit the same local model.
PERSONAS = {
    "project":    "You are a Project Assistant. Help plan, scope, and organize software projects: breaking down tasks, suggesting structure, and tracking progress. Be concise and practical.",
    "cyber":      "You are a Cyber Security Assistant. Explain security concepts, common vulnerabilities, safe practices, and tools clearly. Never provide instructions for causing real-world harm; focus on defense, learning, and best practices.",
    "assignment": "You are an Assignment Assistant. Help the user understand assignment requirements, plan their approach, and check their work. Encourage learning over doing the work for them.",
    "research":   "You are a Research Assistant. Help find angles, structure findings, summarize sources, and organize research clearly and rigorously.",
    "study":      "You are a Study Assistant. Help explain concepts clearly, create study plans, quiz the user, and reinforce learning with examples.",
    "python":     "You are a Python Assistant. Help write, debug, and explain Python code with clear, correct, idiomatic examples.",
    "webdev":     "You are a Web Development Assistant. Help with HTML, CSS, JavaScript, and general front-end/back-end web development questions.",
    "sql":        "You are a SQL Assistant. Help write, optimize, and explain SQL queries and database design questions clearly.",
    "data":       "You are a Data Analysis Assistant. Help explore, clean, analyze, and visualize data, and explain statistical concepts simply.",
}
DEFAULT_PERSONA = "You are a helpful assistant."

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# ---------------------------------------------------------------------------
# Sidebar structure — edit this list to add, remove, or rename sections.
# `key` is the URL slug, `icon` mirrors the emoji you used in your sketch.
# ---------------------------------------------------------------------------
SECTIONS = [
    {"key": "project",    "label": "Project Assistant",      "icon": "💻", "group": "assistants"},
    {"key": "cyber",      "label": "Cyber Assistant",        "icon": "🛡", "group": "assistants"},
    {"key": "assignment", "label": "Assignment Assistant",   "icon": "📄", "group": "assistants"},
    {"key": "research",   "label": "Research Assistant",     "icon": "🧠", "group": "assistants"},
    {"key": "study",      "label": "Study Assistant",        "icon": "📚", "group": "assistants"},
    {"key": "python",     "label": "Python Assistant",       "icon": "🐍", "group": "assistants"},
    {"key": "webdev",     "label": "Web Development Assistant", "icon": "🌐", "group": "assistants"},
    {"key": "sql",        "label": "SQL Assistant",          "icon": "🗄", "group": "assistants"},
    {"key": "data",       "label": "Data Analysis Assistant","icon": "📊", "group": "assistants"},
    {"key": "memory",     "label": "Project Memory",         "icon": "📁", "group": "system"},
    {"key": "settings",   "label": "Settings",               "icon": "⚙",  "group": "system"},
]

# Skills shown on the Settings page — matches the checklist you shared.
SKILLS = [
    {"name": "Python", "status": "Continue improving", "done": False},
    {"name": "SQL", "status": "Basics", "done": True},
    {"name": "HTML", "status": "Done", "done": True},
    {"name": "CSS", "status": "Done", "done": True},
    {"name": "JavaScript", "status": "Done", "done": True},
    {"name": "FastAPI", "status": "Done", "done": True},
    {"name": "Git & GitHub", "status": "Done", "done": True},
    {"name": "AI (Ollama, RAG, LLMs)", "status": "Done", "done": True},
]


def get_section(key: str):
    return next((s for s in SECTIONS if s["key"] == key), None)


SECTION_LABELS = {s["key"]: {"label": s["label"], "icon": s["icon"]} for s in SECTIONS}


@app.get("/")
def home(request: Request):
    if not is_authed(request):
        return RedirectResponse("/login")
    return RedirectResponse("/assistant/project")


@app.get("/login")
def login_form(request: Request, error: str = None):
    return templates.TemplateResponse(
        request, "auth.html",
        {"mode": "login", "error": error},
    )


@app.post("/login")
def login_submit(email: str = Form(...), password: str = Form(...), remember: str = Form(None)):
    email = email.strip().lower()
    if not verify_user(email, password):
        return RedirectResponse("/login?error=Wrong+email+or+password", status_code=303)
    resp = RedirectResponse("/assistant/project", status_code=303)
    if remember:
        resp.set_cookie(AUTH_COOKIE, email, max_age=60 * 60 * 24 * 30, httponly=True)
    else:
        resp.set_cookie(AUTH_COOKIE, email, httponly=True)  # session cookie
    return resp


@app.get("/signup")
def signup_form(request: Request, error: str = None):
    return templates.TemplateResponse(
        request, "auth.html",
        {"mode": "signup", "error": error},
    )


@app.post("/signup")
def signup_submit(email: str = Form(...), password: str = Form(...), confirm_password: str = Form(...)):
    email = email.strip().lower()
    users = load_users()

    if not email or not password:
        return RedirectResponse("/signup?error=Email+and+password+required", status_code=303)
    if password != confirm_password:
        return RedirectResponse("/signup?error=Passwords+don%27t+match", status_code=303)
    if email in users:
        return RedirectResponse("/signup?error=That+email+is+already+registered", status_code=303)

    create_user(email, password)
    resp = RedirectResponse("/assistant/project", status_code=303)
    resp.set_cookie(AUTH_COOKIE, email, max_age=60 * 60 * 24 * 30, httponly=True)
    return resp


@app.get("/logout")
def logout():
    resp = RedirectResponse("/login", status_code=303)
    resp.delete_cookie(AUTH_COOKIE)
    return resp


@app.get("/assistant/{key}")
def assistant_page(request: Request, key: str):
    if not is_authed(request):
        return RedirectResponse("/login")

    section = get_section(key) or SECTIONS[0]
    data = load_history()

    return templates.TemplateResponse(
        request,
        "page.html",
        {
            "sections": SECTIONS,
            "active": section,
            "skills": SKILLS if section["key"] == "settings" else None,
            "history": data.get(section["key"], []),
            "all_history": data if section["key"] == "memory" else None,
            "section_labels": SECTION_LABELS,
            "user": current_user(request),
        },
    )


@app.post("/assistant/{key}/message")
def send_message(request: Request, key: str, payload: dict):
    if not is_authed(request):
        return {"reply": "Please sign in first."}
    text = (payload or {}).get("text", "").strip()
    if not text:
        return {"reply": "Type something first."}

    append_message(key, "user", text)
    system_prompt = PERSONAS.get(key, DEFAULT_PERSONA)

    try:
        resp = requests.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text},
                ],
                "stream": False,
            },
            timeout=120,
        )
        resp.raise_for_status()
        data = resp.json()
        reply = data.get("message", {}).get("content", "").strip() or "(empty response from model)"
        append_message(key, "assistant", reply)
        return {"reply": reply}

    except requests.exceptions.ConnectionError:
        return {
            "reply": (
                "Couldn't reach Ollama at localhost:11434. "
                "Make sure the Ollama app (or `ollama serve`) is running, "
                f"and that you've pulled the model with `ollama pull {OLLAMA_MODEL}`."
            )
        }
    except requests.exceptions.Timeout:
        return {"reply": "Ollama took too long to respond. Try a shorter message or a smaller model."}
    except Exception as e:
        return {"reply": f"Something went wrong talking to Ollama: {e}"}
