"""
AI Email Automation Agent — Free IMAP/SMTP + Groq version
No Google Cloud. No OAuth. Just Gmail App Password + Groq API (free).
Now with SQLite persistence — emails survive server restarts.

Author: Ayush Singh Tomar
"""

import os
import imaplib
import smtplib
import email as emaillib
import json
import time
import logging
import sqlite3
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import decode_header

from groq import Groq
from dotenv import load_dotenv

# ── Environment ────────────────────────────────────────────────────────────────
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

GMAIL_ADDRESS  = os.environ["GMAIL_ADDRESS"]
GMAIL_APP_PASS = os.environ["GMAIL_APP_PASS"]
YOUR_NAME      = os.environ.get("YOUR_NAME", "Your Name")
YOUR_ROLE      = os.environ.get("YOUR_ROLE", "Freelance AI Developer")
DB_FILE        = os.environ.get("DB_FILE", "email_agent.db")

# ── Groq client ──────────────────────────────────────────────────────────────
groq_client = Groq(api_key=os.environ["GROQ_API_KEY"])

# ── Constants ─────────────────────────────────────────────────────────────────
IMAP_HOST  = "imap.gmail.com"
SMTP_HOST  = "smtp.gmail.com"
SMTP_PORT  = 587
CATEGORIES = ["lead", "client", "support", "newsletter", "spam", "other"]

# In-memory cache: email_id → { email, analysis, status }
# SQLite is the source of truth; this is just for fast reads during a session
PROCESSED: dict[str, dict] = {}


# ── SQLite setup ──────────────────────────────────────────────────────────────

def init_db() -> None:
    """Create the emails table if it doesn't exist yet."""
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS emails (
                email_id        TEXT PRIMARY KEY,
                timestamp       TEXT,
                from_addr       TEXT,
                to_addr         TEXT,
                subject         TEXT,
                date            TEXT,
                body            TEXT,
                category        TEXT,
                priority        TEXT,
                sentiment       TEXT,
                action_required INTEGER,
                summary         TEXT,
                key_info        TEXT,
                draft_reply     TEXT,
                confidence      REAL,
                status          TEXT DEFAULT 'pending'
            )
        """)
        conn.commit()
    logger.info("SQLite DB ready.")


def save_to_db(email: dict, analysis: dict, status: str = "pending") -> None:
    """Insert or replace a processed email record into SQLite."""
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("""
            INSERT OR REPLACE INTO emails VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
        """, (
            email["id"],
            datetime.utcnow().isoformat(),
            email.get("from", ""),
            email.get("to", ""),
            email.get("subject", ""),
            email.get("date", ""),
            email.get("body", "")[:3000],
            analysis.get("category", "other"),
            analysis.get("priority", "low"),
            analysis.get("sentiment", "neutral"),
            1 if analysis.get("action_required") else 0,
            analysis.get("summary", ""),
            analysis.get("key_info", ""),
            analysis.get("draft_reply", ""),
            float(analysis.get("confidence", 0.0)),
            status,
        ))
        conn.commit()


def update_db_status(email_id: str, status: str) -> None:
    """Update the status of an email record in SQLite."""
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute(
            "UPDATE emails SET status = ? WHERE email_id = ?",
            (status, email_id)
        )
        conn.commit()


def update_db_draft(email_id: str, draft: str) -> None:
    """Update the draft reply of an email record in SQLite."""
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute(
            "UPDATE emails SET draft_reply = ? WHERE email_id = ?",
            (draft, email_id)
        )
        conn.commit()


def load_all_from_db() -> list:
    """
    Load all emails from SQLite into the in-memory PROCESSED cache.
    Called once on server startup so history is always available.
    """
    with sqlite3.connect(DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM emails ORDER BY timestamp DESC"
        ).fetchall()

    loaded = 0
    for row in rows:
        email_id = row["email_id"]
        if email_id in PROCESSED:
            continue
        PROCESSED[email_id] = {
            "email": {
                "id":      email_id,
                "from":    row["from_addr"],
                "to":      row["to_addr"],
                "subject": row["subject"],
                "date":    row["date"],
                "body":    row["body"],
            },
            "analysis": {
                "email_id":        email_id,
                "category":        row["category"],
                "priority":        row["priority"],
                "sentiment":       row["sentiment"],
                "action_required": bool(row["action_required"]),
                "summary":         row["summary"],
                "key_info":        row["key_info"],
                "draft_reply":     row["draft_reply"],
                "confidence":      row["confidence"],
            },
            "status": row["status"],
        }
        loaded += 1

    logger.info(f"Loaded {loaded} email(s) from SQLite into memory.")
    return list(PROCESSED.values())


def get_db_stats() -> dict:
    """Return counts by category, priority, and status from SQLite."""
    with sqlite3.connect(DB_FILE) as conn:
        total     = conn.execute("SELECT COUNT(*) FROM emails").fetchone()[0]
        pending   = conn.execute("SELECT COUNT(*) FROM emails WHERE status='pending'").fetchone()[0]
        sent      = conn.execute("SELECT COUNT(*) FROM emails WHERE status='sent'").fetchone()[0]
        rejected  = conn.execute("SELECT COUNT(*) FROM emails WHERE status='rejected'").fetchone()[0]
        leads     = conn.execute("SELECT COUNT(*) FROM emails WHERE category='lead'").fetchone()[0]
        high_pri  = conn.execute("SELECT COUNT(*) FROM emails WHERE priority='high'").fetchone()[0]
    return {
        "total": total,
        "pending": pending,
        "sent": sent,
        "rejected": rejected,
        "leads": leads,
        "high_priority": high_pri,
    }


# ── Gmail helpers ─────────────────────────────────────────────────────────────

def connect_imap() -> imaplib.IMAP4_SSL:
    mail = imaplib.IMAP4_SSL(IMAP_HOST)
    mail.login(GMAIL_ADDRESS, GMAIL_APP_PASS)
    return mail


def decode_str(value) -> str:
    parts = decode_header(value or "")
    result = []
    for part, enc in parts:
        if isinstance(part, bytes):
            result.append(part.decode(enc or "utf-8", errors="replace"))
        else:
            result.append(part)
    return "".join(result)


def fetch_unread_emails(max_results: int = 10) -> list:
    mail = connect_imap()
    mail.select("inbox")
    _, data = mail.search(None, "UNSEEN")
    ids = data[0].split()[-max_results:]

    emails = []
    for uid in ids:
        _, msg_data = mail.fetch(uid, "(RFC822)")
        raw = msg_data[0][1]
        msg = emaillib.message_from_bytes(raw)
        body = _extract_body(msg)
        emails.append({
            "id":      uid.decode(),
            "from":    decode_str(msg.get("From", "")),
            "to":      decode_str(msg.get("To", "")),
            "subject": decode_str(msg.get("Subject", "(no subject)")),
            "date":    msg.get("Date", ""),
            "body":    body[:3000],
        })

    mail.logout()
    logger.info(f"Fetched {len(emails)} unread email(s).")
    return emails


def _extract_body(msg) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            if (
                part.get_content_type() == "text/plain"
                and not part.get("Content-Disposition")
            ):
                return part.get_payload(decode=True).decode("utf-8", errors="replace")
        return ""
    return msg.get_payload(decode=True).decode("utf-8", errors="replace")


def mark_as_read(uid: str) -> None:
    mail = connect_imap()
    mail.select("inbox")
    mail.store(uid, "+FLAGS", "\\Seen")
    mail.logout()


def send_email(to: str, subject: str, body: str) -> None:
    msg = MIMEMultipart("alternative")
    msg["From"]    = GMAIL_ADDRESS
    msg["To"]      = to
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.ehlo()
        server.starttls()
        server.login(GMAIL_ADDRESS, GMAIL_APP_PASS)
        server.sendmail(GMAIL_ADDRESS, to, msg.as_string())

    logger.info(f"Reply sent → {to} | Subject: {subject}")


# ── Groq analysis ─────────────────────────────────────────────────────────────

def analyze_email(email: dict, retries: int = 3) -> dict:
    prompt = _build_prompt(email)

    for attempt in range(1, retries + 1):
        try:
            response = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}]
            )
            raw = response.choices[0].message.content.strip()
            raw = raw.replace("```json", "").replace("```", "").strip()
            result = json.loads(raw)
            result["email_id"] = email["id"]
            logger.info(
                f"Analyzed '{email['subject'][:50]}' → "
                f"{result.get('category')} / {result.get('priority')}"
            )
            return result

        except json.JSONDecodeError as e:
            logger.warning(f"Attempt {attempt}: JSON parse error — {e}")
        except Exception as e:
            logger.warning(f"Attempt {attempt}: Groq error — {e}")

        wait = 4 * (2 ** (attempt - 1))
        logger.info(f"Retrying in {wait}s…")
        time.sleep(wait)

    logger.error(f"Could not analyze '{email['subject']}' after {retries} attempts.")
    return _fallback_analysis(email["id"])


def _build_prompt(email: dict) -> str:
    return f"""You are an email assistant for {YOUR_NAME}, a {YOUR_ROLE}.

Analyze this email and respond ONLY with valid JSON — no markdown, no explanation, no backticks.

EMAIL:
From: {email['from']}
Subject: {email['subject']}
Date: {email['date']}
Body:
{email['body']}

Respond with exactly this JSON structure:
{{
  "category": "<one of: {', '.join(CATEGORIES)}>",
  "priority": "<one of: high, medium, low>",
  "summary": "<1-2 sentence summary of what this email is about>",
  "key_info": "<important names, dates, numbers, or action items>",
  "sentiment": "<positive | neutral | negative>",
  "action_required": <true | false>,
  "draft_reply": "<a professional reply signed off as {YOUR_NAME}. Leave empty string if spam or newsletter.>",
  "confidence": <0.0 to 1.0>
}}"""


def _fallback_analysis(email_id: str) -> dict:
    return {
        "email_id":        email_id,
        "category":        "other",
        "priority":        "low",
        "summary":         "Could not analyze — will retry next cycle.",
        "key_info":        "",
        "sentiment":       "neutral",
        "action_required": False,
        "draft_reply":     "",
        "confidence":      0.0,
    }


# ── Core agent cycle ──────────────────────────────────────────────────────────

def run_agent_cycle() -> list:
    """
    Main loop: fetch unread emails → analyze → save to SQLite → cache in memory.
    Skips emails already in SQLite (survived restart) or in-memory cache.
    """
    logger.info("════ Agent cycle started ════")
    init_db()

    emails = fetch_unread_emails(max_results=10)
    new_count = 0

    for email in emails:
        if email["id"] in PROCESSED:
            logger.info(f"Skipping already-processed: {email['subject'][:50]}")
            continue

        analysis = analyze_email(email)
        save_to_db(email, analysis, status="pending")
        mark_as_read(email["id"])

        PROCESSED[email["id"]] = {
            "email":    email,
            "analysis": analysis,
            "status":   "pending",
        }
        new_count += 1
        time.sleep(1)

    logger.info(
        f"════ Cycle done. New: {new_count} | "
        f"Total session: {len(PROCESSED)} ════"
    )
    return list(PROCESSED.values())


def send_approved_reply(email_id: str) -> bool:
    """Send the AI-drafted reply and persist status to SQLite."""
    item = PROCESSED.get(email_id)
    if not item:
        logger.warning(f"send_approved_reply: '{email_id}' not found.")
        return False

    draft = item["analysis"].get("draft_reply", "").strip()
    if not draft:
        logger.warning(f"send_approved_reply: no draft for '{email_id}'.")
        return False

    email = item["email"]
    send_email(
        to=email["from"],
        subject=f"Re: {email['subject']}",
        body=draft,
    )

    PROCESSED[email_id]["status"] = "sent"
    update_db_status(email_id, "sent")
    return True
