# 📧 AI Email Automation Agent

An AI-powered email agent that reads your Gmail, categorizes emails, drafts professional replies using LLaMA 3, and lets you approve or reject them from a clean dashboard — all without touching Google Cloud.

![Dashboard Preview](https://i.imgur.com/placeholder.png)

---

## 🚀 What It Does

- **Reads** unread emails from Gmail via IMAP
- **Analyzes** each email using Groq (LLaMA 3.3 70B) — category, priority, sentiment, summary
- **Drafts** a professional reply signed with your name
- **Logs** everything to a local CSV file
- **Dashboard** to review, edit, approve, or reject drafts before sending
- **Auto-runs** every 5 minutes in the background

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| AI / LLM | [Groq API](https://console.groq.com) — LLaMA 3.3 70B (free tier) |
| Backend | Python, FastAPI, APScheduler |
| Email | IMAP (read) + SMTP (send) — no Google Cloud needed |
| Frontend | React + Vite |
| Logging | CSV (local) |

---

## 📁 Project Structure

```
email-agent/
├── backend/
│   ├── agent.py        # Core AI logic — fetch, analyze, send
│   ├── server.py       # FastAPI REST API
│   ├── requirements.txt
│   └── .env.example
└── frontend/
    └── src/
        └── App.jsx     # React dashboard
```

---

## ⚡ Quick Start

### 1. Clone the repo
```bash
git clone https://github.com/YOUR_USERNAME/email-agent.git
cd email-agent
```

### 2. Get your free API keys

**Groq API** (free, no credit card):
- Go to [console.groq.com](https://console.groq.com)
- Create an account → API Keys → Create key

**Gmail App Password** (2 min setup):
- Go to [myaccount.google.com/security](https://myaccount.google.com/security)
- Enable 2-Step Verification if not already on
- Search "App Passwords" → create one named `email-agent`
- Copy the 16-character password

### 3. Configure environment
```bash
cd backend
copy .env.example .env   # Windows
# cp .env.example .env   # Mac/Linux
```

Fill in your `.env`:
```env
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxx
GMAIL_ADDRESS=you@gmail.com
GMAIL_APP_PASS=abcd efgh ijkl mnop
YOUR_NAME=Your Full Name
YOUR_ROLE=AI Developer
LOG_FILE=email_log.csv
POLL_INTERVAL=5
```

### 4. Install dependencies & start backend
```bash
pip install -r requirements.txt
python -m uvicorn server:app --reload --port 8000
```

### 5. Start frontend
```bash
cd ../frontend
npm install
npm run dev
```

### 6. Open the dashboard
Go to **http://localhost:5173** and click **Run Now**.

---

## 🎯 How It Works

```
Gmail Inbox (IMAP)
      ↓
  Fetch unread emails
      ↓
  Groq API (LLaMA 3.3 70B)
  → category, priority, sentiment, summary, draft reply
      ↓
  Store in memory + log to CSV
      ↓
  React Dashboard
  → Review · Edit · Approve & Send / Reject
      ↓
  Gmail SMTP → reply sent
```

---

## 📊 Email Categories

| Category | Description |
|----------|-------------|
| 📈 Lead | Potential job/business opportunity |
| 🤝 Client | Existing client communication |
| ⚙ Support | Help or technical requests |
| ≡ Newsletter | Newsletters and subscriptions |
| ✕ Spam | Spam or unwanted email |
| ◉ Other | Everything else |

---

## 🔒 Security Notes

- Your `.env` file is **never committed** to Git (listed in `.gitignore`)
- The Gmail App Password only allows email access — it cannot be used to log into your Google account
- All data stays local — nothing is sent to external servers except the email content to Groq for analysis

---

## 🧠 Interview Talking Points

**"What does this project do?"**
> It's an AI agent that automates email triage. It connects to Gmail via IMAP, sends each unread email to LLaMA 3 through Groq's API for analysis, gets back structured JSON with category/priority/summary/draft reply, and surfaces everything on a React dashboard where I can approve replies with one click.

**"Why Groq instead of OpenAI?"**
> Groq has a free tier with no rate limits for my use case, and their inference speed is significantly faster — ideal for batch processing emails. The model quality on LLaMA 3.3 70B is more than sufficient for structured classification tasks.

**"How does the backend work?"**
> FastAPI serves 6 REST endpoints. An APScheduler job runs `run_agent_cycle()` every 5 minutes automatically. Emails are stored in an in-memory dict keyed by IMAP UID, and logged to CSV for persistence across dashboard reloads.

---

## 📌 Roadmap

- [ ] Deploy backend to Railway/Render
- [ ] Deploy frontend to Vercel
- [ ] Add email threading (reply-to-reply)
- [ ] Slack/WhatsApp notification on high-priority emails
- [ ] Multi-account support

---

## 👤 Author

**Ayush Singh Tomar**
- GitHub: [@YOUR_USERNAME](https://github.com/YOUR_USERNAME)
- LinkedIn: [linkedin.com/in/YOUR_PROFILE](https://linkedin.com/in/YOUR_PROFILE)

---

*Built as part of my AI Developer portfolio. This is the exact tool I use for managing recruiter outreach during my job search.*
