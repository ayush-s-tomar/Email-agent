# 📧 AI Email Automation Agent

An AI-powered email agent that reads your Gmail, categorizes emails, drafts professional replies using LLaMA 3.3, and lets you approve or reject them from a clean dashboard — all without touching Google Cloud.

🔗 **Live Demo:** https://email-agent-xi-drab.vercel.app

---

## 🚀 What It Does

- **Reads** unread emails from Gmail via IMAP
- **Analyzes** each email using Groq (LLaMA 3.3 70B) — category, priority, sentiment, summary
- **Drafts** a professional reply signed with your name
- **Composes** personalized cold emails with one click using LLaMA 3.3
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
git clone https://github.com/ayush-s-tomar/Email-agent.git
cd Email-agent
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
YOUR_ROLE=Freelance AI Developer
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
| 🛠️ Support | Help or technical requests |
| 📰 Newsletter | Newsletters and subscriptions |
| 🚫 Spam | Spam or unwanted email |
| 📬 Other | Everything else |

---

## 🔒 Security Notes

- Your `.env` file is **never committed** to Git (listed in `.gitignore`)
- The Gmail App Password only allows email access — it cannot be used to log into your Google account
- All data stays local — nothing is sent to external servers except the email content to Groq for analysis

---

## 🧠 Interview Talking Points

**"What does this project do?"**
> It's an AI agent that automates email triage. It connects to Gmail via IMAP, sends each unread email to LLaMA 3.3 through Groq's API for analysis, gets back structured JSON with category/priority/summary/draft reply, and surfaces everything on a React dashboard where I can approve replies with one click.

**"Why Groq instead of OpenAI?"**
> Groq has a completely free tier with no credit card required, and their inference speed is significantly faster — ideal for batch processing emails. LLaMA 3.3 70B is more than sufficient for structured classification tasks.

**"Why IMAP instead of Gmail API?"**
> IMAP works with just a Gmail App Password — no Google Cloud project, no OAuth consent screen, no credentials.json. It's simpler to set up and easier for anyone to replicate from the README.

**"How does the backend work?"**
> FastAPI serves 6 REST endpoints. An APScheduler job runs `run_agent_cycle()` every 5 minutes automatically. Emails are stored in an in-memory dict keyed by IMAP UID, and logged to CSV for persistence across dashboard reloads.

**"What is the cold email composer?"**
> It's a built-in feature where you enter a recipient's name, company, and target role — LLaMA 3.3 generates a personalized 80-word cold email instantly. This is literally the tool I use to send outreach emails to recruiters.

---

## 📌 Roadmap

- [x] Deploy frontend to Vercel
- [x] Cold email composer with LLaMA 3.3
- [ ] Persistent storage with SQLite
- [ ] Email threading (reply-to-reply)
- [ ] Slack/WhatsApp notification on high-priority emails
- [ ] Multi-account support

---

## 👤 Author

**Ayush Singh Tomar**
- GitHub: [@ayush-s-tomar](https://github.com/ayush-s-tomar)
- LinkedIn: [linkedin.com/in/ayush-singh-tomar-4151b0282](https://linkedin.com/in/ayush-singh-tomar-4151b0282)

---

*Built as part of my AI Developer portfolio. This is the exact tool I use for managing recruiter and client outreach.*
