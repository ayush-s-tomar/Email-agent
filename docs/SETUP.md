# AI Email Automation Agent — Setup Guide

## What this does
Reads your Gmail inbox → Claude categorizes each email and drafts a reply →
you review + approve in a dashboard → sends via Gmail → logs everything to Google Sheets.

---

## Prerequisites
- Python 3.10+
- Node.js 18+
- A Google account (Gmail + Google Sheets)
- Anthropic API key: https://console.anthropic.com

---

## Step 1 — Google Cloud Setup (15 min, one-time)

1. Go to https://console.cloud.google.com
2. Create a new project (e.g. "email-agent")
3. Enable these APIs:
   - **Gmail API** (search in the API library)
   - **Google Sheets API**
4. Go to **APIs & Services → Credentials**
5. Click **Create Credentials → OAuth 2.0 Client ID**
   - Application type: **Desktop app**
   - Name it anything
6. Download the JSON → rename it to `credentials.json`
7. Place `credentials.json` inside the `backend/` folder
8. Go to **OAuth consent screen** → add your Gmail as a test user

---

## Step 2 — Google Sheet

1. Create a new Google Sheet at https://sheets.google.com
2. Copy the Sheet ID from the URL:
   `https://docs.google.com/spreadsheets/d/**SHEET_ID_HERE**/edit`
3. Save this ID — you'll need it for `.env`

---

## Step 3 — Backend setup

```bash
cd backend
cp .env.example .env
# Fill in your values in .env

pip install -r requirements.txt

# First run — opens a browser for Google OAuth
python -c "from agent import get_google_credentials; get_google_credentials()"
# Approve access in the browser. token.pickle is created.

# Start the API server
uvicorn server:app --reload --port 8000
```

---

## Step 4 — Frontend setup

```bash
cd frontend

# If you don't have a Vite project yet:
npm create vite@latest . -- --template react
# (choose React, then JavaScript)

# Install deps
npm install

# Copy App.jsx into src/App.jsx (already done if you cloned this repo)

# Start the dashboard
npm run dev
# Opens at http://localhost:5173
```

---

## Step 5 — First run

1. Open http://localhost:5173
2. Click **Run Now** — the agent fetches your unread emails
3. Each email appears as a card with:
   - Category (lead, client, support, etc.)
   - Priority (high / medium / low)
   - AI-generated summary
   - Draft reply from Claude
4. Edit the draft if needed, then click **Approve & Send**
5. Check your Google Sheet — every email is logged automatically

---

## Environment variables (.env)

| Variable | Description |
|---|---|
| `ANTHROPIC_API_KEY` | Your Anthropic key (starts with sk-ant-) |
| `SPREADSHEET_ID` | Google Sheet ID from the URL |
| `YOUR_NAME` | Your name (used in Claude's reply drafts) |
| `YOUR_ROLE` | e.g. "Freelance AI Developer" |
| `YOUR_EMAIL` | Your Gmail address |
| `POLL_INTERVAL` | Minutes between automatic checks (default: 5) |

---

## Project structure

```
email-agent/
├── backend/
│   ├── agent.py          ← Core: Gmail + Claude + Sheets logic
│   ├── server.py         ← FastAPI REST API
│   ├── requirements.txt
│   ├── .env.example
│   ├── credentials.json  ← YOU add this (Google OAuth)
│   └── token.pickle      ← Auto-generated after first auth
└── frontend/
    └── src/
        └── App.jsx       ← React dashboard
```

---

## API endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/emails` | All processed emails |
| POST | `/run` | Trigger manual agent cycle |
| POST | `/approve/{id}` | Send draft reply |
| POST | `/reject/{id}` | Reject (no send) |
| PUT | `/draft/{id}` | Edit draft before sending |
| GET | `/stats` | Summary statistics |
| GET | `/health` | Server health check |

---

## Cold email pitch angle

> "I built an AI email agent that reads my Gmail, has Claude categorize and draft replies, 
> and logs everything to Google Sheets. I used it to send you this email."

This is your proof of work. Show the GitHub repo + a screenshot of the dashboard.

---

## Customizing the Claude prompt

Edit the `analyze_email()` function in `agent.py`. The prompt controls:
- Categories (add your own)
- Reply tone/style
- What "key info" means for your context
- Signature / sign-off in drafts

---

## Production tips

- **Deploy backend**: Railway, Render, or a $5 VPS with `systemd` service
- **Deploy frontend**: Vercel or Netlify (free tier)
- **Persistence**: Replace the in-memory `PROCESSED` dict with SQLite or Postgres
- **Webhooks**: Use Gmail push notifications instead of polling for near-instant response
- **Rate limits**: The agent sleeps 0.5s between emails — safe for free tier

---

## Troubleshooting

**`credentials.json not found`** → Download it from Google Cloud Console (Step 1)

**`token.pickle invalid`** → Delete token.pickle and re-run the auth step

**`400 Bad Request` on send** → Your OAuth app may not have Gmail send scope. Re-run auth.

**Claude returns non-JSON** → Check ANTHROPIC_API_KEY is set correctly. The agent handles parse errors gracefully.

**Sheet not updating** → Confirm SPREADSHEET_ID is correct and you have editor access to the sheet.
