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

# ─── Auto-scheduler ────────────────────────────────────────────────────────────

POLL_INTERVAL_MINUTES = int(os.environ.get("POLL_INTERVAL", "5"))

scheduler = BackgroundScheduler()
scheduler.add_job(agent.run_agent_cycle, "interval", minutes=POLL_INTERVAL_MINUTES)
scheduler.start()

# ─── Models ───────────────────────────────────────────────────────────────────

class DraftUpdate(BaseModel):
    draft_reply: str

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
    agent.update_csv_status(email_id, "rejected")
    return {"message": "Marked as rejected", "email_id": email_id}


@app.put("/draft/{email_id}")
def update_draft(email_id: str, body: DraftUpdate):
    """Edit the AI-drafted reply before sending."""
    item = agent.PROCESSED.get(email_id)
    if not item:
        raise HTTPException(status_code=404, detail="Email not found")

    agent.PROCESSED[email_id]["analysis"]["draft_reply"] = body.draft_reply
    return {"message": "Draft updated", "email_id": email_id}


@app.get("/stats")
def get_stats():
    """Summary statistics for the dashboard header."""
    items = list(agent.PROCESSED.values())
    stats = {
        "total":       len(items),
        "pending":     sum(1 for i in items if i["status"] == "pending"),
        "sent":        sum(1 for i in items if i["status"] == "sent"),
        "rejected":    sum(1 for i in items if i["status"] == "rejected"),
        "by_category": {},
        "by_priority": {"high": 0, "medium": 0, "low": 0},
    }
    for item in items:
        cat = item["analysis"].get("category", "other")
        stats["by_category"][cat] = stats["by_category"].get(cat, 0) + 1
        pri = item["analysis"].get("priority", "low")
        stats["by_priority"][pri] = stats["by_priority"].get(pri, 0) + 1

    return stats

@app.get("/debug")
def debug():
    try:
        import imaplib
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(os.environ.get("GMAIL_ADDRESS", "NOT SET"),
                   os.environ.get("GMAIL_APP_PASS", "NOT SET"))
        mail.select("inbox")
        _, data = mail.search(None, "UNSEEN")
        count = len(data[0].split())
        mail.logout()
        return {"status": "ok", "unread_count": count,
                "gmail": os.environ.get("GMAIL_ADDRESS", "NOT SET")}
    except Exception as e:
        return {"status": "error", "error": str(e),
                "gmail": os.environ.get("GMAIL_ADDRESS", "NOT SET")}
@app.get("/health")
def health():
    return {"status": "ok", "poll_interval_minutes": POLL_INTERVAL_MINUTES}