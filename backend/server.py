"""
FastAPI server — bridges the agent and the React dashboard.
Endpoints:
  GET  /emails          -> list all processed emails (optional ?account= filter)
  GET  /accounts        -> list configured Gmail accounts
  POST /run             -> trigger one agent cycle
  POST /approve/{id}    -> send the draft reply
  POST /reject/{id}     -> mark as rejected (no send)
  PUT  /draft/{id}      -> edit a draft before sending
  GET  /stats           -> summary stats
  POST /tone/{id}       -> regenerate draft with a specific tone
  POST /compose         -> generate a cold email
  GET  /health          -> full health check with cycle stats and uptime
"""

import json
import os
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from apscheduler.schedulers.background import BackgroundScheduler

import agent

app = FastAPI(title="Email Agent API", version="1.0.0")

_SERVER_START = datetime.now(timezone.utc).isoformat()

DEFAULT_ORIGINS = "https://email-agent-xi-drab.vercel.app,http://localhost:5173"
ALLOWED_ORIGINS = os.environ.get("ALLOWED_ORIGINS", DEFAULT_ORIGINS).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup_event():
    agent.init_db()
    agent.load_all_from_db()

POLL_INTERVAL_MINUTES = int(os.environ.get("POLL_INTERVAL", "5"))
scheduler = BackgroundScheduler()
scheduler.add_job(agent.run_agent_cycle, "interval", minutes=POLL_INTERVAL_MINUTES)
scheduler.start()

class DraftUpdate(BaseModel):
    draft_reply: str

class ComposeRequest(BaseModel):
    name: str
    company: str
    role: str
    context: str = ""

class ToneRequest(BaseModel):
    tone: str


@app.get("/accounts")
def list_accounts():
    return {"accounts": [{"email": a["email"], "name": a["name"]} for a in agent.ACCOUNTS]}


@app.get("/emails")
def list_emails(account: str = Query(default=None)):
    items = list(agent.PROCESSED.values())
    if account:
        items = [i for i in items if i["email"].get("account_email") == account]
    priority_order = {"high": 0, "medium": 1, "low": 2}
    items.sort(key=lambda x: priority_order.get(x["analysis"].get("priority", "low"), 2))
    return {"emails": items, "total": len(items)}


@app.post("/run")
async def run_cycle(background_tasks: BackgroundTasks):
    background_tasks.add_task(agent.run_agent_cycle)
    return {"message": "Agent cycle started"}


@app.post("/approve/{email_id}")
def approve_email(email_id: str):
    item = agent.PROCESSED.get(email_id)
    if not item:
        raise HTTPException(status_code=404, detail="Email not found")
    if item["status"] == "sent":
        raise HTTPException(status_code=400, detail="Already sent")
    success = agent.send_approved_reply(email_id)
    if not success:
        raise HTTPException(status_code=400, detail="No draft reply available or send failed")
    return {"message": "Reply sent", "email_id": email_id}


@app.post("/reject/{email_id}")
def reject_email(email_id: str):
    item = agent.PROCESSED.get(email_id)
    if not item:
        raise HTTPException(status_code=404, detail="Email not found")
    agent.PROCESSED[email_id]["status"] = "rejected"
    agent.update_db_status(email_id, "rejected")
    return {"message": "Marked as rejected", "email_id": email_id}


@app.put("/draft/{email_id}")
def update_draft(email_id: str, body: DraftUpdate):
    item = agent.PROCESSED.get(email_id)
    if not item:
        raise HTTPException(status_code=404, detail="Email not found")
    agent.PROCESSED[email_id]["analysis"]["draft_reply"] = body.draft_reply
    agent.update_db_draft(email_id, body.draft_reply)
    return {"message": "Draft updated", "email_id": email_id}


@app.post("/tone/{email_id}")
def change_tone(email_id: str, body: ToneRequest):
    valid_tones = {"professional", "friendly", "concise"}
    if body.tone.lower() not in valid_tones:
        raise HTTPException(status_code=400, detail=f"Invalid tone. Choose from: {', '.join(valid_tones)}")
    item = agent.PROCESSED.get(email_id)
    if not item:
        raise HTTPException(status_code=404, detail="Email not found")
    if item["status"] == "sent":
        raise HTTPException(status_code=400, detail="Email already sent — cannot change tone")
    new_draft = agent.regenerate_draft(email_id, body.tone)
    if not new_draft:
        raise HTTPException(status_code=500, detail="Failed to regenerate draft")
    return {"draft_reply": new_draft, "tone": body.tone, "email_id": email_id}


@app.get("/stats")
def get_stats():
    return agent.get_db_stats()


@app.post("/compose")
def compose_email(body: ComposeRequest):
    prompt = f"""Write a short, personalized cold email from {agent.YOUR_NAME} ({agent.YOUR_ROLE}) to {body.name} at {body.company} for a {body.role} position.

Additional context: {body.context if body.context else 'None'}

Rules:
- Max 80 words
- Sound human, not robotic
- Mention something specific about reaching out for this role
- End with a soft CTA like 'Would love to connect'
- Sign off as {agent.YOUR_NAME}
- Return ONLY a JSON object with two keys: "subject" and "body"
- No markdown, no backticks, just raw JSON"""

    try:
        result = agent.groq_client.chat.completions.create(
            model=agent.GROQ_MODEL, messages=[{"role": "user", "content": prompt}]
        )
        raw = result.choices[0].message.content.strip()
        raw = raw.replace("```json", "").replace("```", "").strip()
        parsed = json.loads(raw)
        return {"subject": parsed.get("subject", ""), "email": parsed.get("body", raw)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
def health():
    """Full health check — includes cycle stats, error history, and uptime.
    The dashboard polls this to show the live status strip."""
    cs = agent.CYCLE_STATS
    return {
        "status":                "ok",
        "server_start":          _SERVER_START,
        "poll_interval_minutes": POLL_INTERVAL_MINUTES,
        "accounts":              len(agent.ACCOUNTS),
        "last_run":              cs["last_run"],
        "last_success":          cs["last_success"],
        "last_new_count":        cs["last_new_count"],
        "errors_last_cycle":     cs["errors_last_cycle"],
        "total_errors":          cs["total_errors"],
        "total_cycles":          cs["total_cycles"],
    }