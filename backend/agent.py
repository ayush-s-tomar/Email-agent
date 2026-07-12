"""
AI Email Automation Agent — Free IMAP/SMTP + Groq version
No Google Cloud. No OAuth. Just Gmail App Password + Groq API (free).

Now with SQLite persistence    — emails survive server restarts.
Now with email threading       — replies land in the same Gmail thread.
Now with thread grouping       — related emails are grouped by conversation.
Now with tone selector         — regenerate drafts as Professional / Friendly / Concise.
Now with Slack alerts          — instant notifications for high-priority and lead emails.
Now with configurable alerts   — tune priority threshold and alert categories via .env.
Now with multi-account support — poll and triage multiple Gmail inboxes from one dashboard.
Now with structured logging    — rotating log files + per-cycle error tracking.

Author: Ayush Singh Tomar
"""

import os
import re
import json
import imaplib
import smtplib
import email as emaillib
import time
import logging
import logging.handlers
import sqlite3
import urllib.request
from contextlib import contextmanager
from datetime import datetime, timezone
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import decode_header

from groq import Groq
from dotenv import load_dotenv

load_dotenv()

# ── Logging — console + rotating file (10 MB max, 3 backups) ──────────────────
LOG_FILE = os.environ.get("LOG_FILE_PATH", "email_agent.log")

_formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

_console_handler = logging.StreamHandler()
_console_handler.setFormatter(_formatter)

_file_handler = logging.handlers.RotatingFileHandler(
    LOG_FILE, maxBytes=10 * 1024 * 1024, backupCount=3, encoding="utf-8"
)
_file_handler.setFormatter(_formatter)

logging.basicConfig(level=logging.INFO, handlers=[_console_handler, _file_handler])
logger = logging.getLogger(__name__)

YOUR_NAME = os.environ.get("YOUR_NAME", "Your Name")
YOUR_ROLE = os.environ.get("YOUR_ROLE", "Freelance AI Developer")
DB_FILE   = os.environ.get("DB_FILE", "email_agent.db")

# ── Cycle stats — read by /health endpoint ────────────────────────────────────
# Tracks the outcome of every agent cycle so the dashboard can surface health.
CYCLE_STATS: dict = {
    "last_run":          None,   # ISO timestamp of most recent cycle start
    "last_success":      None,   # ISO timestamp of last fully successful cycle
    "last_new_count":    0,      # how many new emails were processed last cycle
    "errors_last_cycle": [],     # list of error strings from the last cycle
    "total_errors":      0,      # cumulative error count since server start
    "total_cycles":      0,      # cumulative cycles run since server start
}

# ── Multi-account config ───────────────────────────────────────────────────────
def load_accounts() -> list:
    raw = os.environ.get("GMAIL_ACCOUNTS", "").strip()
    if raw:
        try:
            accounts = json.loads(raw)
            for a in accounts:
                if not a.get("email") or not a.get("app_pass"):
                    raise ValueError(f"Account missing 'email' or 'app_pass': {a}")
                a.setdefault("name", a["email"].split("@")[0].capitalize())
            logger.info(f"Multi-account mode: {[a['email'] for a in accounts]}")
            return accounts
        except Exception as e:
            logger.error(f"Failed to parse GMAIL_ACCOUNTS: {e}. Falling back to single account.")

    addr = os.environ.get("GMAIL_ADDRESS", "")
    pw   = os.environ.get("GMAIL_APP_PASS", "")
    if not addr or not pw:
        raise RuntimeError("No Gmail credentials. Set GMAIL_ADDRESS + GMAIL_APP_PASS in .env")
    logger.info(f"Single-account mode: {addr}")
    return [{"email": addr, "app_pass": pw, "name": YOUR_NAME}]

ACCOUNTS: list = load_accounts()

# ── Slack config ───────────────────────────────────────────────────────────────
SLACK_WEBHOOK = os.environ.get("SLACK_WEBHOOK", "")
_raw_priorities = os.environ.get("SLACK_ALERT_PRIORITIES", "high")
SLACK_ALERT_PRIORITIES: set = {p.strip().lower() for p in _raw_priorities.split(",") if p.strip()}
_raw_categories = os.environ.get("SLACK_ALERT_CATEGORIES", "lead")
SLACK_ALERT_CATEGORIES: set = {c.strip().lower() for c in _raw_categories.split(",") if c.strip()}

logger.info(
    f"Slack alerts active — priorities={SLACK_ALERT_PRIORITIES}, categories={SLACK_ALERT_CATEGORIES}"
    if SLACK_WEBHOOK else "Slack alerts disabled (no SLACK_WEBHOOK set)"
)

# ── Groq client ───────────────────────────────────────────────────────────────
groq_client = Groq(api_key=os.environ["GROQ_API_KEY"])
GROQ_MODEL  = "llama-3.3-70b-versatile"

# ── Constants ─────────────────────────────────────────────────────────────────
IMAP_HOST  = "imap.gmail.com"
SMTP_HOST  = "smtp.gmail.com"
SMTP_PORT  = 587
CATEGORIES = ["lead", "client", "support", "newsletter", "spam", "other"]
_REPLY_PREFIX_RE = re.compile(r'^(re|fwd?|fw)\s*:\s*', re.IGNORECASE)

TONE_INSTRUCTIONS = {
    "professional": (
        "Write in a formal, polished tone. Use complete sentences, "
        "proper salutations, and a respectful sign-off. Sound confident and businesslike."
    ),
    "friendly": (
        "Write in a warm, approachable tone. Be conversational and personable "
        "while staying professional. Use natural language, not stiff corporate speak."
    ),
    "concise": (
        "Write the shortest possible reply that still covers everything needed. "
        "No filler words. Get to the point immediately. Max 3 sentences."
    ),
}

PROCESSED: dict = {}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def _record_error(msg: str) -> None:
    """Append an error to the current cycle's error list and bump the total."""
    CYCLE_STATS["errors_last_cycle"].append(msg)
    CYCLE_STATS["total_errors"] += 1
    logger.error(msg)


def compute_thread_key(subject: str) -> str:
    s = subject.strip()
    while True:
        cleaned = _REPLY_PREFIX_RE.sub("", s).strip()
        if cleaned == s:
            break
        s = cleaned
    return s.lower() or "untitled"


# ── SQLite setup ──────────────────────────────────────────────────────────────

@contextmanager
def get_db():
    conn = sqlite3.connect(DB_FILE, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS emails (
                email_id        TEXT PRIMARY KEY,
                timestamp       TEXT,
                account_email   TEXT,
                from_addr       TEXT,
                to_addr         TEXT,
                subject         TEXT,
                date            TEXT,
                body            TEXT,
                message_id      TEXT,
                references_hdr  TEXT,
                thread_key      TEXT,
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
        for col, coltype in [
            ("message_id",    "TEXT"),
            ("references_hdr","TEXT"),
            ("thread_key",    "TEXT"),
            ("account_email", "TEXT"),
        ]:
            try:
                conn.execute(f"ALTER TABLE emails ADD COLUMN {col} {coltype}")
            except sqlite3.OperationalError:
                pass

        conn.execute("CREATE INDEX IF NOT EXISTS idx_status     ON emails(status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_priority   ON emails(priority)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_category   ON emails(category)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_timestamp  ON emails(timestamp)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_thread_key ON emails(thread_key)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_account    ON emails(account_email)")

    logger.info("SQLite DB ready (WAL mode, indexes applied).")


def save_to_db(email: dict, analysis: dict, status: str = "pending") -> bool:
    try:
        with get_db() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO emails VALUES (
                    ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?
                )
            """, (
                email["id"],
                _now_iso(),
                email.get("account_email", ""),
                email.get("from", ""),
                email.get("to", ""),
                email.get("subject", ""),
                email.get("date", ""),
                email.get("body", "")[:3000],
                email.get("message_id", ""),
                email.get("references", ""),
                email.get("thread_key", ""),
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
        return True
    except sqlite3.Error as e:
        _record_error(f"save_to_db failed for '{email.get('id')}': {e}")
        return False


def update_db_status(email_id: str, status: str) -> bool:
    try:
        with get_db() as conn:
            conn.execute("UPDATE emails SET status=? WHERE email_id=?", (status, email_id))
        return True
    except sqlite3.Error as e:
        _record_error(f"update_db_status failed for '{email_id}': {e}")
        return False


def update_db_draft(email_id: str, draft: str) -> bool:
    try:
        with get_db() as conn:
            conn.execute("UPDATE emails SET draft_reply=? WHERE email_id=?", (draft, email_id))
        return True
    except sqlite3.Error as e:
        _record_error(f"update_db_draft failed for '{email_id}': {e}")
        return False


def load_all_from_db() -> list:
    try:
        with get_db() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM emails ORDER BY timestamp DESC").fetchall()
    except sqlite3.Error as e:
        _record_error(f"load_all_from_db failed: {e}")
        return []

    loaded = 0
    for row in rows:
        email_id = row["email_id"]
        if email_id in PROCESSED:
            continue
        PROCESSED[email_id] = {
            "email": {
                "id":            email_id,
                "account_email": row["account_email"] or "",
                "from":          row["from_addr"],
                "to":            row["to_addr"],
                "subject":       row["subject"],
                "date":          row["date"],
                "body":          row["body"],
                "message_id":    row["message_id"] or "",
                "references":    row["references_hdr"] or "",
                "thread_key":    row["thread_key"] or compute_thread_key(row["subject"] or ""),
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
    try:
        with get_db() as conn:
            total    = conn.execute("SELECT COUNT(*) FROM emails").fetchone()[0]
            pending  = conn.execute("SELECT COUNT(*) FROM emails WHERE status='pending'").fetchone()[0]
            sent     = conn.execute("SELECT COUNT(*) FROM emails WHERE status='sent'").fetchone()[0]
            rejected = conn.execute("SELECT COUNT(*) FROM emails WHERE status='rejected'").fetchone()[0]
            leads    = conn.execute("SELECT COUNT(*) FROM emails WHERE category='lead'").fetchone()[0]
            high_pri = conn.execute("SELECT COUNT(*) FROM emails WHERE priority='high'").fetchone()[0]
            threads  = conn.execute(
                "SELECT COUNT(DISTINCT thread_key) FROM emails WHERE thread_key IS NOT NULL AND thread_key != ''"
            ).fetchone()[0]
        return {"total": total, "pending": pending, "sent": sent, "rejected": rejected,
                "leads": leads, "high_priority": high_pri, "threads": threads}
    except sqlite3.Error as e:
        _record_error(f"get_db_stats failed: {e}")
        return {"total": 0, "pending": 0, "sent": 0, "rejected": 0,
                "leads": 0, "high_priority": 0, "threads": 0}


# ── Slack alerts ──────────────────────────────────────────────────────────────

def should_alert(analysis: dict) -> bool:
    if not SLACK_WEBHOOK:
        return False
    return (
        analysis.get("priority", "").lower() in SLACK_ALERT_PRIORITIES or
        analysis.get("category", "").lower() in SLACK_ALERT_CATEGORIES
    )


def send_slack_alert(email: dict, analysis: dict) -> None:
    try:
        cat = analysis.get("category", "other")
        pri = analysis.get("priority", "low")
        summary = analysis.get("summary", "")
        conf = int(float(analysis.get("confidence", 0)) * 100)
        acct = email.get("account_email", "")

        pri_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(pri, "⚪")
        cat_icon = "↗" if cat == "lead" else "◈"
        reasons = []
        if pri in SLACK_ALERT_PRIORITIES: reasons.append(f"priority is {pri}")
        if cat in SLACK_ALERT_CATEGORIES: reasons.append(f"category is {cat}")

        payload = {"blocks": [
            {"type": "header", "text": {"type": "plain_text", "text": f"{pri_icon} {pri.upper()} priority · {cat} email"}},
            {"type": "section", "fields": [
                {"type": "mrkdwn", "text": f"*From:*\n{email.get('from', '')}"},
                {"type": "mrkdwn", "text": f"*Category:*\n{cat_icon} {cat}"},
                {"type": "mrkdwn", "text": f"*Subject:*\n{email.get('subject', '')}"},
                {"type": "mrkdwn", "text": f"*Confidence:*\n{conf}%"},
            ]},
            {"type": "section", "text": {"type": "mrkdwn", "text": f"*Summary:*\n{summary}"}},
            {"type": "context", "elements": [{"type": "mrkdwn", "text": f"Account: {acct} · Alerted because: {' · '.join(reasons)}"}]},
            {"type": "actions", "elements": [{"type": "button", "text": {"type": "plain_text", "text": "Open Dashboard"},
              "url": "https://email-agent-xi-drab.vercel.app", "style": "primary"}]},
        ]}

        req = urllib.request.Request(SLACK_WEBHOOK, data=json.dumps(payload).encode(),
                                     headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=5)
        logger.info(f"Slack alert sent for '{email.get('subject', '')[:50]}'")
    except Exception as e:
        logger.warning(f"Slack alert failed (non-critical): {e}")


# ── Gmail helpers ─────────────────────────────────────────────────────────────

def connect_imap(account: dict) -> imaplib.IMAP4_SSL:
    mail = imaplib.IMAP4_SSL(IMAP_HOST)
    mail.login(account["email"], account["app_pass"])
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


def fetch_unread_emails(account: dict, max_results: int = 10) -> list:
    """Fetch unread emails for one account. Returns [] on any IMAP error so the
    cycle continues with remaining accounts instead of crashing entirely."""
    try:
        mail = connect_imap(account)
        mail.select("inbox")
        _, data = mail.search(None, "UNSEEN")
        ids = data[0].split()[-max_results:]

        emails = []
        for uid in ids:
            try:
                _, msg_data = mail.fetch(uid, "(RFC822)")
                raw = msg_data[0][1]
                msg = emaillib.message_from_bytes(raw)
                body    = _extract_body(msg)
                subject = decode_str(msg.get("Subject", "(no subject)"))
                namespaced_id = f"{account['email']}:{uid.decode()}"
                emails.append({
                    "id":            namespaced_id,
                    "account_email": account["email"],
                    "from":          decode_str(msg.get("From", "")),
                    "to":            decode_str(msg.get("To", "")),
                    "subject":       subject,
                    "date":          msg.get("Date", ""),
                    "body":          body[:3000],
                    "message_id":    msg.get("Message-ID", ""),
                    "references":    msg.get("References", ""),
                    "thread_key":    compute_thread_key(subject),
                    "_imap_uid":     uid.decode(),
                })
            except Exception as e:
                _record_error(f"[{account['email']}] Failed to parse email UID {uid}: {e}")

        mail.logout()
        logger.info(f"[{account['email']}] Fetched {len(emails)} unread email(s).")
        return emails

    except Exception as e:
        _record_error(f"[{account['email']}] IMAP fetch failed: {e}")
        return []


def _extract_body(msg) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain" and not part.get("Content-Disposition"):
                return part.get_payload(decode=True).decode("utf-8", errors="replace")
        return ""
    return msg.get_payload(decode=True).decode("utf-8", errors="replace")


def mark_as_read(account: dict, imap_uid: str) -> None:
    try:
        mail = connect_imap(account)
        mail.select("inbox")
        mail.store(imap_uid, "+FLAGS", "\\Seen")
        mail.logout()
    except Exception as e:
        logger.warning(f"[{account['email']}] mark_as_read failed (non-critical): {e}")


def send_email(account: dict, to: str, subject: str, body: str,
               message_id: str = None, references: str = None) -> None:
    msg = MIMEMultipart("alternative")
    msg["From"]    = account["email"]
    msg["To"]      = to
    msg["Subject"] = subject

    if message_id:
        msg["In-Reply-To"] = message_id
        msg["References"]  = f"{references or ''} {message_id}".strip()

    msg.attach(MIMEText(body, "plain"))

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.ehlo()
        server.starttls()
        server.login(account["email"], account["app_pass"])
        server.sendmail(account["email"], to, msg.as_string())

    logger.info(f"[{account['email']}] Reply sent -> {to} | Subject: {subject}")


# ── Groq analysis ─────────────────────────────────────────────────────────────

def analyze_email(email: dict, retries: int = 3) -> dict:
    prompt = _build_prompt(email)

    for attempt in range(1, retries + 1):
        try:
            response = groq_client.chat.completions.create(
                model=GROQ_MODEL, messages=[{"role": "user", "content": prompt}]
            )
            raw = response.choices[0].message.content.strip()
            raw = raw.replace("```json", "").replace("```", "").strip()
            result = json.loads(raw)
            result["email_id"] = email["id"]
            logger.info(f"[{email.get('account_email','')}] Analyzed '{email['subject'][:50]}' -> "
                        f"{result.get('category')} / {result.get('priority')}")
            return result

        except json.JSONDecodeError as e:
            logger.warning(f"Attempt {attempt}: JSON parse error -- {e}")
        except Exception as e:
            logger.warning(f"Attempt {attempt}: Groq error -- {e}")

        wait = 4 * (2 ** (attempt - 1))
        logger.info(f"Retrying in {wait}s...")
        time.sleep(wait)

    _record_error(f"Could not analyze '{email['subject']}' after {retries} attempts.")
    return _fallback_analysis(email["id"])


def regenerate_draft(email_id: str, tone: str) -> str:
    item = PROCESSED.get(email_id)
    if not item:
        logger.warning(f"regenerate_draft: '{email_id}' not found.")
        return ""

    tone = tone.lower().strip()
    tone_instruction = TONE_INSTRUCTIONS.get(tone, TONE_INSTRUCTIONS["professional"])
    email = item["email"]

    prompt = f"""You are an email assistant for {YOUR_NAME}, a {YOUR_ROLE}.

Rewrite a reply to the email below using this specific tone:
TONE: {tone.upper()} -- {tone_instruction}

EMAIL:
From: {email['from']}
Subject: {email['subject']}
Body:
{email['body'][:2000]}

Rules:
- Reply ONLY with the email body text. No subject line. No JSON. No explanation.
- Sign off as {YOUR_NAME}.
- Match the tone instruction strictly."""

    try:
        response = groq_client.chat.completions.create(
            model=GROQ_MODEL, messages=[{"role": "user", "content": prompt}]
        )
        new_draft = response.choices[0].message.content.strip()
        PROCESSED[email_id]["analysis"]["draft_reply"] = new_draft
        update_db_draft(email_id, new_draft)
        logger.info(f"Regenerated draft for '{email['subject'][:50]}' -> tone: {tone}")
        return new_draft
    except Exception as e:
        _record_error(f"regenerate_draft error: {e}")
        return ""


def _build_prompt(email: dict) -> str:
    return f"""You are an email assistant for {YOUR_NAME}, a {YOUR_ROLE}.

Analyze this email and respond ONLY with valid JSON -- no markdown, no explanation, no backticks.

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
    return {"email_id": email_id, "category": "other", "priority": "low",
            "summary": "Could not analyze -- will retry next cycle.", "key_info": "",
            "sentiment": "neutral", "action_required": False, "draft_reply": "", "confidence": 0.0}


# ── Core agent cycle ──────────────────────────────────────────────────────────

def run_agent_cycle() -> list:
    logger.info(f"Agent cycle started for {len(ACCOUNTS)} account(s)")
    init_db()

    # Reset per-cycle error list; keep running totals
    CYCLE_STATS["last_run"]          = _now_iso()
    CYCLE_STATS["errors_last_cycle"] = []
    CYCLE_STATS["total_cycles"]     += 1

    new_count = 0

    for account in ACCOUNTS:
        emails = fetch_unread_emails(account, max_results=10)
        for email in emails:
            if email["id"] in PROCESSED:
                logger.info(f"Skipping already-processed: {email['subject'][:50]}")
                continue

            analysis = analyze_email(email)
            if not save_to_db(email, analysis, status="pending"):
                # Error already recorded inside save_to_db via _record_error
                continue

            mark_as_read(account, email["_imap_uid"])

            if should_alert(analysis):
                send_slack_alert(email, analysis)

            PROCESSED[email["id"]] = {"email": email, "analysis": analysis, "status": "pending"}
            new_count += 1
            time.sleep(1)

    CYCLE_STATS["last_new_count"] = new_count

    # Only mark last_success if no errors occurred this cycle
    if not CYCLE_STATS["errors_last_cycle"]:
        CYCLE_STATS["last_success"] = _now_iso()

    logger.info(f"Cycle done. New: {new_count} | Errors: {len(CYCLE_STATS['errors_last_cycle'])} | Total session: {len(PROCESSED)}")
    return list(PROCESSED.values())


def send_approved_reply(email_id: str) -> bool:
    item = PROCESSED.get(email_id)
    if not item:
        logger.warning(f"send_approved_reply: '{email_id}' not found.")
        return False

    draft = item["analysis"].get("draft_reply", "").strip()
    if not draft:
        logger.warning(f"send_approved_reply: no draft for '{email_id}'.")
        return False

    email = item["email"]
    acct_email = email.get("account_email", "")
    account = next((a for a in ACCOUNTS if a["email"] == acct_email), ACCOUNTS[0])

    try:
        send_email(
            account=account,
            to=email["from"],
            subject=f"Re: {email['subject']}",
            body=draft,
            message_id=email.get("message_id", ""),
            references=email.get("references", ""),
        )
    except Exception as e:
        _record_error(f"send_approved_reply SMTP failed for '{email_id}': {e}")
        return False

    PROCESSED[email_id]["status"] = "sent"
    update_db_status(email_id, "sent")
    return True