from fastapi import FastAPI, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from datetime import datetime
import hashlib
import json
import os
import secrets
import string
import threading

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_DIR = "/data"
TICKETS_FILE = os.path.join(DATA_DIR, "tickets.json")
USERS_FILE = os.path.join(DATA_DIR, "users.json")
_file_lock = threading.Lock()


def _ensure_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def load_tickets():
    if os.path.exists(TICKETS_FILE):
        with open(TICKETS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_tickets(tickets):
    _ensure_dir()
    with open(TICKETS_FILE, "w", encoding="utf-8") as f:
        json.dump(tickets, f, ensure_ascii=False, indent=2)


def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_users(users):
    _ensure_dir()
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)


def _generate_access_code() -> str:
    chars = string.ascii_uppercase + string.digits
    return "-".join(
        "".join(secrets.choice(chars) for _ in range(4)) for _ in range(3)
    )


class TicketRequest(BaseModel):
    subject: str
    block_number: int
    score: int
    total: int
    device_info: str
    fingerprint: str
    nickname: str = ""
    access_code: str = ""
    started_at: str = ""
    finished_at: str = ""


class RegisterRequest(BaseModel):
    nickname: str
    phone: str = ""


class LoginRequest(BaseModel):
    access_code: str


@app.post("/api/users/register")
async def register_user(req: RegisterRequest):
    nick = req.nickname.strip()
    if len(nick) < 2:
        return JSONResponse(status_code=400, content={"error": "Ник должен быть не менее 2 символов"})

    with _file_lock:
        users = load_users()
        for u in users:
            if u["nickname"].lower() == nick.lower():
                return JSONResponse(status_code=409, content={"error": "Этот ник уже занят"})

        access_code = _generate_access_code()
        phone = req.phone.strip()
        if len(phone) < 5:
            return JSONResponse(status_code=400, content={"error": "Введите номер телефона"})

        user = {
            "id": f"U-{secrets.token_hex(4).upper()}",
            "nickname": nick,
            "phone": phone,
            "access_code": access_code,
            "registered_at": datetime.now().isoformat(),
        }
        users.append(user)
        save_users(users)

    return {"status": "ok", "user": user}


@app.post("/api/users/login")
async def login_user(req: LoginRequest):
    code = req.access_code.strip().upper()
    with _file_lock:
        users = load_users()
        for u in users:
            if u["access_code"] == code:
                tickets = load_tickets()
                user_tickets = [t for t in tickets if t.get("access_code") == code]
                return {"status": "ok", "user": u, "tickets": user_tickets}
    return JSONResponse(status_code=404, content={"error": "Неверный код доступа"})


@app.post("/api/tickets")
async def issue_ticket(ticket_req: TicketRequest, request: Request):
    ip = request.headers.get("x-forwarded-for", request.client.host)
    if "," in ip:
        ip = ip.split(",")[0].strip()

    with _file_lock:
        tickets = load_tickets()

        for t in tickets:
            if (
                t.get("access_code") == ticket_req.access_code
                and t["subject"] == ticket_req.subject
                and t["block_number"] == ticket_req.block_number
            ):
                return JSONResponse(
                    status_code=409,
                    content={"error": "duplicate", "ticket": t},
                )

        seq = len(tickets) + 1
        rand_part = secrets.token_hex(5).upper()
        raw = f"{seq}-{rand_part}-{ticket_req.fingerprint}-{datetime.now().isoformat()}"
        check = hashlib.sha256(raw.encode()).hexdigest()[:8].upper()
        ticket_id = f"T-{rand_part}-{check}"

        ticket = {
            "id": ticket_id,
            "subject": ticket_req.subject,
            "block_number": ticket_req.block_number,
            "score": ticket_req.score,
            "total": ticket_req.total,
            "percentage": round(ticket_req.score / ticket_req.total * 100, 1) if ticket_req.total > 0 else 0,
            "device_info": ticket_req.device_info,
            "fingerprint": ticket_req.fingerprint,
            "nickname": ticket_req.nickname,
            "access_code": ticket_req.access_code,
            "ip": ip,
            "issued_at": datetime.now().isoformat(),
            "started_at": ticket_req.started_at,
            "finished_at": ticket_req.finished_at,
        }

        tickets.append(ticket)
        save_tickets(tickets)

    return {"status": "ok", "ticket": ticket}


def _check_auth(authorization: str | None) -> bool:
    if not authorization:
        return False
    expected = os.environ.get("ADMIN_PASSWORD", "admin2024")
    if authorization.startswith("Bearer "):
        return authorization[7:] == expected
    return authorization == expected


@app.get("/api/tickets")
async def get_tickets(authorization: str | None = Header(default=None)):
    if not _check_auth(authorization):
        return JSONResponse(status_code=401, content={"error": "unauthorized"})
    with _file_lock:
        tickets = load_tickets()
    return {"tickets": tickets}


@app.get("/api/users")
async def get_users(authorization: str | None = Header(default=None)):
    if not _check_auth(authorization):
        return JSONResponse(status_code=401, content={"error": "unauthorized"})
    with _file_lock:
        users = load_users()
        tickets = load_tickets()

    result = []
    for u in users:
        user_tickets = [t for t in tickets if t.get("access_code") == u["access_code"]]
        result.append({
            **u,
            "tickets_count": len(user_tickets),
            "tickets": user_tickets,
        })
    return {"users": result}


@app.get("/api/leaderboard")
async def get_leaderboard():
    with _file_lock:
        users = load_users()
        tickets = load_tickets()

    board = []
    for u in users:
        user_tickets = [t for t in tickets if t.get("access_code") == u["access_code"]]
        board.append({
            "nickname": u["nickname"],
            "tickets_count": len(user_tickets),
            "avg_score": (
                round(sum(t["percentage"] for t in user_tickets) / len(user_tickets), 1)
                if user_tickets
                else 0
            ),
        })
    board.sort(key=lambda x: (-x["tickets_count"], -x["avg_score"]))
    return {"leaderboard": board}


@app.get("/api/stats")
async def get_stats(authorization: str | None = Header(default=None)):
    if not _check_auth(authorization):
        return JSONResponse(status_code=401, content={"error": "unauthorized"})
    with _file_lock:
        tickets = load_tickets()
        users = load_users()
    unique_ips = set(t["ip"] for t in tickets)
    unique_devices = set(t["fingerprint"] for t in tickets)
    return {
        "total_tickets": len(tickets),
        "total_users": len(users),
        "unique_ips": len(unique_ips),
        "unique_devices": len(unique_devices),
        "tickets_by_subject": {
            "biochem": len([t for t in tickets if t["subject"] == "biochem"]),
            "physiology": len([t for t in tickets if t["subject"] == "physiology"]),
        },
    }


@app.get("/health")
async def health():
    return {"status": "ok"}
