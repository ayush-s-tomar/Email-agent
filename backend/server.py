"""
FastAPI server — bridges the agent and the React dashboard.
Endpoints:
  GET  /emails          → list all processed emails
  POST /run             → trigger one agent cycle
  POST /approve/{id}    → send the draft reply
  POST /reject/{id}     → mark as rejected (no send)
  PUT  /draft/{id}      → edit a draft before sending
  GET  /stats           → summary stats
  GET  /health          → health check
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from apscheduler.schedulers.background import BackgroundScheduler
import agent
import os

app = FastAPI(title="Email Agent API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Startup: init DB and load history ────────────────────────────────────────

@app.on_event("startup")
def startup_event():
    """On server start: create DB table and load all past emails into memory."""
    agent.init_db()
    agent.load_all_from_db()

# ─── Auto-scheduler ───────────────────────────────────────────────────────────

POLL_INTERVAL_MINUTES = int(os.environ.get("POLL_INTERVAL", "5"))

scheduler = BackgroundScheduler()
scheduler.add_job(agent.run_agent_cycle, "interval", minutes=POLL_INTERVAL_MINUTES)
scheduler.start()

# ─── Models ───────────────────────────────────────────────────────────────────

class DraftUpdate(BaseModel):
    draft_reply: str

class ComposeRequest(BaseModel):
    name: str
    company: str
    role: str
    context: str = ""

# ─── Routes ───────────────────────────────────────────────────────────────────

@app.get("/emails")
def list_emails():
    """Return all processed emails with their analysis and status."""
    items = list(agent.PROCESSED.values())
    priority_order = {"high": 0, "medium": 1, "low": 2}
    items.sort(key=lambda x: priority_order.get(x["analysis"].get("priority", "low"), 2))
    return {"emails": items, "total": len(items)}


@app.post("/run")
async def run_cycle(background_tasks: BackgroundTasks):
    """Manually trigger an agent cycle (runs async so it doesn't block)."""
    background_tasks.add_task(agent.run_agent_cycle)
    return {"message": "Agent cycle started"}


@app.post("/approve/{email_id}")
def approve_email(email_id: str):
    """Approve and send the draft reply."""
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
    """Reject — mark as rejected, no email sent."""
    item = agent.PROCESSED.get(email_id)
    if not item:
        raise HTTPException(status_code=404, detail="Email not found")

    agent.PROCESSED[email_id]["status"] = "rejected"
    agent.update_db_status(email_id, "rejected")
    return {"message": "Marked as rejected", "email_id": email_id}


@app.put("/draft/{email_id}")
def update_draft(email_id: str, body: DraftUpdate):
    """Edit the AI-drafted reply before sending."""
    item = agent.PROCESSED.get(email_id)
    if not item:
        raise HTTPException(status_code=404, detail="Email not found")

    agent.PROCESSED[email_id]["analysis"]["draft_reply"] = body.draft_reply
    agent.update_db_draft(email_id, body.draft_reply)
    return {"message": "Draft updated", "email_id": email_id}


@app.get("/stats")
def get_stats():
    """Summary statistics pulled directly from SQLite — always accurate."""
    return agent.get_db_stats()


@app.post("/compose")
def compose_email(body: ComposeRequest):
    """Generate a personalized cold email using Groq."""
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
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}]
        )
        raw = result.choices[0].message.content.strip()
        raw = raw.replace("```json", "").replace("```", "").strip()
        parsed = __import__("json").loads(raw)
        return {"subject": parsed.get("subject", ""), "email": parsed.get("body", raw)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
def health():
    return {"status": "ok", "poll_interval_minutes": POLL_INTERVAL_MINUTES}
