"""
AI Email Automation Agent — Free IMAP/SMTP + Groq version
No Google Cloud. No OAuth. Just Gmail App Password + Groq API (free).

Author: Ayush Singh Tomar
"""

import os
import imaplib
import smtplib
import email as emaillib
import json
import time
import logging
import csv
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
LOG_FILE       = os.environ.get("LOG_FILE", "email_log.csv")

# ── Groq client ─────────────────────────────────────────────────────────────────
groq_client = Groq(api_key=os.environ["GROQ_API_KEY"])

# ── Constants ───────────────────────────────────────────────────────────────────
IMAP_HOST  = "imap.gmail.com"
SMTP_HOST  = "smtp.gmail.com"
SMTP_PORT  = 587
CATEGORIES = ["lead", "client", "support", "newsletter", "spam", "other"]

# In-memory store: email_id → { email, analysis, status }
PROCESSED: dict[str, dict] = {}


# ── Gmail helpers ────────────────────────────────────────────────────────────────

def connect_imap() -> imaplib.IMAP4_SSL:
    """Open an authenticated IMAP connection."""
    mail = imaplib.IMAP4_SSL(IMAP_HOST)
    mail.login(GMAIL_ADDRESS, GMAIL_APP_PASS)
    return mail


def decode_str(value) -> str:
    """Decode a potentially encoded email header into plain text."""
    parts = decode_header(value or "")
    result = []
    for part, enc in parts:
        if isinstance(part, bytes):
            result.append(part.decode(enc or "utf-8", errors="replace"))
        else:
            result.append(part)
    return "".join(result)


def fetch_unread_emails(max_results: int = 10) -> list:
    """
    Fetch the most recent `max_results` unread emails from Gmail inbox.
    Returns a list of email dicts with keys: id, from, to, subject, date, body.
    """
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
    """Pull plain-text body from a (possibly multipart) email."""
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
    """Mark a single email as read by its IMAP UID."""
    mail = connect_imap()
    mail.select("inbox")
    mail.store(uid, "+FLAGS", "\\Seen")
    mail.logout()


def send_email(to: str, subject: str, body: str) -> None:
    """Send a plain-text reply via SMTP."""
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


# ── Groq analysis ────────────────────────────────────────────────────────────────

def analyze_email(email: dict, retries: int = 3) -> dict:
    """
    Send an email to Groq/Llama for categorization and draft reply.
    Retries up to `retries` times on failure, with exponential back-off.
    Returns a structured dict with category, priority, summary, draft_reply, etc.
    """
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
            logger.info(f"Analyzed '{email['subject'][:50]}' → {result.get('category')} / {result.get('priority')}")
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


# ── CSV logging ──────────────────────────────────────────────────────────────────

CSV_HEADERS = [
    "Timestamp", "Email ID", "From", "Subject", "Category", "Priority",
    "Sentiment", "Action Required", "Summary", "Key Info",
    "Draft Reply", "Status", "Confidence",
]


def ensure_csv() -> None:
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(CSV_HEADERS)


def log_to_csv(email: dict, analysis: dict, status: str = "pending") -> None:
    ensure_csv()
    row = [
        datetime.utcnow().isoformat(),
        email["id"],
        email["from"],
        email["subject"],
        analysis.get("category", ""),
        analysis.get("priority", ""),
        analysis.get("sentiment", ""),
        analysis.get("action_required", ""),
        analysis.get("summary", ""),
        analysis.get("key_info", ""),
        analysis.get("draft_reply", "")[:300],
        status,
        analysis.get("confidence", ""),
    ]
    with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(row)


def update_csv_status(email_id: str, status: str) -> None:
    ensure_csv()
    rows = []
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        for row in csv.reader(f):
            if len(row) > 1 and row[1] == email_id:
                row[11] = status
            rows.append(row)
    with open(LOG_FILE, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows(rows)


# ── Core agent cycle ─────────────────────────────────────────────────────────────

def run_agent_cycle() -> list:
    """
    Main loop: fetch unread emails → analyze with Groq → log → store in memory.
    Skips emails already processed in this session.
    """
    logger.info("════ Agent cycle started ════")
    ensure_csv()

    emails = fetch_unread_emails(max_results=10)
    new_count = 0

    for email in emails:
        if email["id"] in PROCESSED:
            logger.info(f"Skipping already-processed: {email['subject'][:50]}")
            continue

        analysis = analyze_email(email)
        log_to_csv(email, analysis, status="pending")
        mark_as_read(email["id"])

        PROCESSED[email["id"]] = {
            "email":    email,
            "analysis": analysis,
            "status":   "pending",
        }
        new_count += 1
        time.sleep(1)  # Groq is fast, 1s gap is plenty

    logger.info(f"════ Cycle done. New: {new_count} | Total session: {len(PROCESSED)} ════")
    return list(PROCESSED.values())


def send_approved_reply(email_id: str) -> bool:
    """
    Send the AI-drafted reply for a given email_id and mark it as sent.
    Returns True on success, False if email not found or draft is empty.
    """
    item = PROCESSED.get(email_id)
    if not item:
        logger.warning(f"send_approved_reply: '{email_id}' not found in session.")
        return False

    draft = item["analysis"].get("draft_reply", "").strip()
    if not draft:
        logger.warning(f"send_approved_reply: no draft reply for '{email_id}'.")
        return False

    email = item["email"]
    send_email(
        to=email["from"],
        subject=f"Re: {email['subject']}",
        body=draft,
    )

    PROCESSED[email_id]["status"] = "sent"
    update_csv_status(email_id, "sent")
    return True
