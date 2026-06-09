import { useState, useEffect, useCallback } from "react";

const API = "https://onlooker-reunite-spiny.ngrok-free.dev";

const HEADERS = {
  "ngrok-skip-browser-warning": "true",
  "Content-Type": "application/json",
};

const CATEGORY_ICONS = {
  lead: "↗", client: "◈", support: "⚙",
  newsletter: "≡", spam: "✕", other: "◉",
};

const CATEGORY_COLOR = {
  lead:       { bg: "#0ff2b210", border: "#0ff2b2", text: "#0ff2b2" },
  client:     { bg: "#3b82f610", border: "#3b82f6", text: "#60a5fa" },
  support:    { bg: "#f59e0b10", border: "#f59e0b", text: "#fbbf24" },
  newsletter: { bg: "#8b5cf610", border: "#8b5cf6", text: "#a78bfa" },
  spam:       { bg: "#ef444410", border: "#ef4444", text: "#f87171" },
  other:      { bg: "#ffffff08", border: "#ffffff20", text: "#9ca3af" },
};

const PRIORITY_DOT = { high: "#ef4444", medium: "#f59e0b", low: "#22c55e" };

const STATUS_STYLE = {
  pending:  { label: "Pending",  color: "#f59e0b" },
  sent:     { label: "Sent",     color: "#22c55e" },
  rejected: { label: "Rejected", color: "#ef4444" },
};

const css = `
  @import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Syne:wght@600;700;800&family=DM+Sans:wght@300;400;500&display=swap');
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: #080a0f; color: #e2e8f0; font-family: 'DM Sans', sans-serif; min-height: 100vh; }
  ::-webkit-scrollbar { width: 4px; }
  ::-webkit-scrollbar-track { background: transparent; }
  ::-webkit-scrollbar-thumb { background: #ffffff15; border-radius: 99px; }

  .topbar { position: sticky; top: 0; z-index: 100; background: #080a0fcc; backdrop-filter: blur(20px); border-bottom: 1px solid #ffffff0d; padding: 0 32px; height: 60px; display: flex; align-items: center; gap: 12px; }
  .logo { font-family: 'Syne', sans-serif; font-weight: 800; font-size: 17px; letter-spacing: -0.03em; color: #fff; display: flex; align-items: center; gap: 10px; }
  .logo-dot { width: 8px; height: 8px; border-radius: 50%; background: #0ff2b2; box-shadow: 0 0 12px #0ff2b2; animation: pulse 2s infinite; }
  @keyframes pulse { 0%, 100% { opacity: 1; transform: scale(1); } 50% { opacity: 0.6; transform: scale(0.85); } }
  .sync-label { font-family: 'DM Mono', monospace; font-size: 10px; color: #ffffff30; letter-spacing: 0.08em; }
  .compose-btn { padding: 8px 18px; background: transparent; color: #0ff2b2; border: 1px solid #0ff2b230; border-radius: 6px; font-family: 'DM Sans', sans-serif; font-size: 13px; font-weight: 500; cursor: pointer; transition: all 0.2s; }
  .compose-btn:hover { background: #0ff2b210; border-color: #0ff2b2; }
  .run-btn { padding: 8px 20px; background: #0ff2b2; color: #080a0f; border: none; border-radius: 6px; font-family: 'DM Sans', sans-serif; font-size: 13px; font-weight: 500; cursor: pointer; transition: all 0.2s; }
  .run-btn:hover:not(:disabled) { background: #2fffc0; transform: translateY(-1px); box-shadow: 0 4px 20px #0ff2b240; }
  .run-btn:disabled { background: #ffffff15; color: #ffffff40; cursor: not-allowed; transform: none; box-shadow: none; }

  .main { max-width: 900px; margin: 0 auto; padding: 32px 24px; }
  .stats-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 28px; }
  .stat-card { background: #ffffff06; border: 1px solid #ffffff0d; border-radius: 10px; padding: 18px 20px; transition: border-color 0.2s; }
  .stat-card:hover { border-color: #ffffff20; }
  .stat-label { font-family: 'DM Mono', monospace; font-size: 9px; letter-spacing: 0.15em; color: #ffffff35; margin-bottom: 8px; text-transform: uppercase; }
  .stat-value { font-family: 'DM Mono', monospace; font-size: 30px; font-weight: 700; color: #fff; line-height: 1; }
  .stat-card.highlight-pending .stat-value { color: #f59e0b; }
  .stat-card.highlight-sent .stat-value { color: #22c55e; }
  .stat-card.highlight-rejected .stat-value { color: #ef4444; }

  .filters { display: flex; gap: 6px; margin-bottom: 20px; flex-wrap: wrap; }
  .filter-btn { padding: 5px 14px; border-radius: 99px; border: 1px solid #ffffff15; background: transparent; color: #ffffff50; font-size: 12px; font-family: 'DM Sans', sans-serif; cursor: pointer; transition: all 0.15s; text-transform: capitalize; }
  .filter-btn:hover { border-color: #ffffff30; color: #ffffff80; }
  .filter-btn.active { border-color: #0ff2b2; color: #0ff2b2; background: #0ff2b210; }

  .email-card { background: #0d1117; border: 1px solid #ffffff0d; border-radius: 12px; padding: 20px 22px; margin-bottom: 12px; transition: border-color 0.2s; animation: slideIn 0.25s ease forwards; }
  @keyframes slideIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
  .email-card:hover { border-color: #ffffff18; }
  .email-card.done { opacity: 0.45; }
  .card-header { display: flex; align-items: flex-start; gap: 14px; margin-bottom: 14px; }
  .cat-icon { width: 36px; height: 36px; border-radius: 8px; display: flex; align-items: center; justify-content: center; font-size: 15px; font-weight: 700; flex-shrink: 0; font-family: 'DM Mono', monospace; }
  .card-meta { flex: 1; min-width: 0; }
  .card-subject { font-family: 'Syne', sans-serif; font-size: 14px; font-weight: 600; color: #f1f5f9; margin-bottom: 5px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .card-from { font-size: 12px; color: #ffffff40; display: flex; align-items: center; gap: 8px; }
  .priority-dot { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; }
  .badges { display: flex; align-items: center; gap: 6px; margin-left: auto; flex-shrink: 0; }
  .badge { font-family: 'DM Mono', monospace; font-size: 9px; letter-spacing: 0.1em; padding: 3px 8px; border-radius: 4px; text-transform: uppercase; border: 1px solid; }
  .summary-box { background: #ffffff05; border: 1px solid #ffffff08; border-radius: 8px; padding: 12px 14px; font-size: 12.5px; color: #94a3b8; line-height: 1.65; margin-bottom: 14px; }
  .summary-box strong { color: #cbd5e1; font-weight: 500; }
  .draft-section { margin-bottom: 14px; }
  .draft-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; }
  .draft-label { font-family: 'DM Mono', monospace; font-size: 9px; letter-spacing: 0.15em; color: #ffffff25; text-transform: uppercase; }
  .edit-btn { font-size: 11px; padding: 3px 10px; border: 1px solid #ffffff15; border-radius: 4px; background: transparent; color: #ffffff40; cursor: pointer; font-family: 'DM Sans', sans-serif; transition: all 0.15s; }
  .edit-btn:hover { border-color: #ffffff30; color: #ffffff70; }
  .draft-text { background: #0a1628; border: 1px solid #1e3a5f; border-radius: 8px; padding: 12px 14px; font-size: 12.5px; color: #93c5fd; white-space: pre-wrap; line-height: 1.65; font-family: 'DM Mono', monospace; }
  .draft-textarea { width: 100%; background: #0a1628; border: 1px solid #3b82f6; border-radius: 8px; padding: 12px 14px; font-size: 12.5px; color: #93c5fd; font-family: 'DM Mono', monospace; line-height: 1.65; resize: vertical; outline: none; }
  .actions { display: flex; gap: 8px; }
  .approve-btn { flex: 1; padding: 10px; background: #0ff2b215; color: #0ff2b2; border: 1px solid #0ff2b230; border-radius: 7px; font-size: 13px; font-weight: 500; cursor: pointer; font-family: 'DM Sans', sans-serif; transition: all 0.15s; }
  .approve-btn:hover:not(:disabled) { background: #0ff2b225; border-color: #0ff2b2; box-shadow: 0 0 16px #0ff2b220; }
  .approve-btn:disabled { opacity: 0.3; cursor: not-allowed; }
  .reject-btn { padding: 10px 18px; background: transparent; color: #ffffff30; border: 1px solid #ffffff10; border-radius: 7px; font-size: 13px; cursor: pointer; font-family: 'DM Sans', sans-serif; transition: all 0.15s; }
  .reject-btn:hover:not(:disabled) { border-color: #ef444440; color: #ef4444; background: #ef444410; }
  .reject-btn:disabled { opacity: 0.3; cursor: not-allowed; }

  .empty-state { text-align: center; padding: 80px 0; border: 1px dashed #ffffff10; border-radius: 12px; }
  .empty-icon { font-family: 'DM Mono', monospace; font-size: 40px; color: #ffffff15; margin-bottom: 16px; }
  .empty-text { font-size: 14px; color: #ffffff25; font-family: 'DM Mono', monospace; letter-spacing: 0.05em; }
  .date-label { font-family: 'DM Mono', monospace; font-size: 10px; color: #ffffff20; white-space: nowrap; }

  /* ── Compose Modal ── */
  .modal-overlay { position: fixed; inset: 0; background: #000000aa; display: flex; align-items: center; justify-content: center; z-index: 999; padding: 24px; }
  .modal { background: #0d1117; border: 1px solid #ffffff18; border-radius: 16px; width: 100%; max-width: 520px; padding: 28px; }
  .modal-title { font-family: 'Syne', sans-serif; font-size: 17px; font-weight: 700; color: #fff; margin-bottom: 6px; }
  .modal-sub { font-size: 12px; color: #ffffff35; font-family: 'DM Mono', monospace; margin-bottom: 24px; }
  .field { margin-bottom: 16px; }
  .field label { display: block; font-size: 11px; color: #ffffff40; letter-spacing: 0.1em; text-transform: uppercase; font-family: 'DM Mono', monospace; margin-bottom: 6px; }
  .field input, .field textarea { width: 100%; background: #080a0f; border: 1px solid #ffffff15; border-radius: 8px; padding: 10px 12px; font-size: 13px; color: #e2e8f0; font-family: 'DM Sans', sans-serif; outline: none; transition: border-color 0.15s; }
  .field input:focus, .field textarea:focus { border-color: #0ff2b250; }
  .field textarea { resize: vertical; min-height: 70px; line-height: 1.5; }
  .modal-actions { display: flex; gap: 8px; margin-top: 20px; }
  .generate-btn { flex: 1; padding: 11px; background: #0ff2b2; color: #080a0f; border: none; border-radius: 8px; font-size: 13px; font-weight: 600; cursor: pointer; font-family: 'DM Sans', sans-serif; transition: all 0.15s; }
  .generate-btn:hover:not(:disabled) { background: #2fffc0; }
  .generate-btn:disabled { opacity: 0.5; cursor: not-allowed; }
  .cancel-btn { padding: 11px 20px; background: transparent; color: #ffffff40; border: 1px solid #ffffff15; border-radius: 8px; font-size: 13px; cursor: pointer; font-family: 'DM Sans', sans-serif; transition: all 0.15s; }
  .cancel-btn:hover { color: #ffffff70; border-color: #ffffff30; }
  .result-box { background: #0a1628; border: 1px solid #1e3a5f; border-radius: 8px; padding: 14px; margin-top: 20px; }
  .result-subject { font-size: 11px; color: #ffffff35; font-family: 'DM Mono', monospace; letter-spacing: 0.1em; margin-bottom: 8px; }
  .result-subject span { color: #60a5fa; }
  .result-email { font-size: 12.5px; color: #93c5fd; white-space: pre-wrap; line-height: 1.65; font-family: 'DM Mono', monospace; }
  .copy-btn { margin-top: 12px; width: 100%; padding: 9px; background: #3b82f610; color: #60a5fa; border: 1px solid #3b82f630; border-radius: 7px; font-size: 12px; cursor: pointer; font-family: 'DM Sans', sans-serif; transition: all 0.15s; }
  .copy-btn:hover { background: #3b82f620; border-color: #3b82f6; }
  .copy-btn.copied { background: #0ff2b215; color: #0ff2b2; border-color: #0ff2b230; }
`;

function ComposeModal({ onClose }) {
  const [form, setForm]       = useState({ name: "", company: "", role: "", context: "" });
  const [result, setResult]   = useState(null);
  const [loading, setLoading] = useState(false);
  const [copied, setCopied]   = useState(false);

  async function handleGenerate() {
    if (!form.name || !form.company || !form.role) return;
    setLoading(true);
    setResult(null);
    try {
      const res = await fetch(`${API}/compose`, {
        method: "POST",
        headers: HEADERS,
        body: JSON.stringify(form),
      });
      const data = await res.json();
      setResult(data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }

  function handleCopy() {
    if (!result) return;
    const full = `Subject: ${result.subject}\n\n${result.email}`;
    navigator.clipboard.writeText(full);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <div className="modal-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="modal">
        <div className="modal-title">✦ Compose cold email</div>
        <div className="modal-sub">Powered by LLaMA 3.3 · 80 words · signed as you</div>

        <div className="field">
          <label>Recipient name</label>
          <input placeholder="e.g. Sarah Chen" value={form.name} onChange={e => setForm({...form, name: e.target.value})} />
        </div>
        <div className="field">
          <label>Company</label>
          <input placeholder="e.g. Stripe" value={form.company} onChange={e => setForm({...form, company: e.target.value})} />
        </div>
        <div className="field">
          <label>Role you're targeting</label>
          <input placeholder="e.g. AI Engineer Intern" value={form.role} onChange={e => setForm({...form, role: e.target.value})} />
        </div>
        <div className="field">
          <label>Extra context (optional)</label>
          <textarea placeholder="e.g. I saw their recent blog post on LLM agents..." value={form.context} onChange={e => setForm({...form, context: e.target.value})} />
        </div>

        <div className="modal-actions">
          <button className="generate-btn" onClick={handleGenerate} disabled={loading || !form.name || !form.company || !form.role}>
            {loading ? "Generating…" : "⟳ Generate email"}
          </button>
          <button className="cancel-btn" onClick={onClose}>Cancel</button>
        </div>

        {result && (
          <div className="result-box">
            <div className="result-subject">SUBJECT: <span>{result.subject}</span></div>
            <div className="result-email">{result.email}</div>
            <button className={`copy-btn ${copied ? "copied" : ""}`} onClick={handleCopy}>
              {copied ? "✓ Copied!" : "Copy email + subject"}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

function EmailCard({ item, onApprove, onReject, onDraftChange }) {
  const { email, analysis, status } = item;
  const [editing, setEditing] = useState(false);
  const [draft, setDraft]     = useState(analysis.draft_reply || "");
  const [loading, setLoading] = useState(false);

  const cat = analysis.category || "other";
  const pri = analysis.priority || "low";
  const catStyle  = CATEGORY_COLOR[cat] || CATEGORY_COLOR.other;
  const isDone    = status === "sent" || status === "rejected";
  const statusInfo = STATUS_STYLE[status] || STATUS_STYLE.pending;

  async function handleApprove() {
    setLoading(true);
    if (editing) await onDraftChange(email.id, draft);
    await onApprove(email.id);
    setLoading(false);
    setEditing(false);
  }

  async function handleReject() {
    setLoading(true);
    await onReject(email.id);
    setLoading(false);
  }

  return (
    <div className={`email-card ${isDone ? "done" : ""}`}>
      <div className="card-header">
        <div className="cat-icon" style={{ background: catStyle.bg, border: `1px solid ${catStyle.border}20`, color: catStyle.text }}>
          {CATEGORY_ICONS[cat]}
        </div>
        <div className="card-meta">
          <div className="card-subject">{email.subject}</div>
          <div className="card-from">
            <div className="priority-dot" style={{ background: PRIORITY_DOT[pri] }} />
            {email.from.replace(/<.*>/, "").trim()}
            <span style={{ color: "#ffffff20" }}>·</span>
            <span style={{ textTransform: "capitalize", color: catStyle.text }}>{cat}</span>
            <span style={{ color: "#ffffff20" }}>·</span>
            <span>{analysis.sentiment}</span>
          </div>
        </div>
        <div className="badges">
          <span className="badge" style={{ color: statusInfo.color, borderColor: `${statusInfo.color}40`, background: `${statusInfo.color}10` }}>
            {statusInfo.label}
          </span>
          <span className="date-label">
            {new Date(email.date).toLocaleDateString("en-GB", { day: "numeric", month: "short" })}
          </span>
        </div>
      </div>

      <div className="summary-box">
        <strong>Summary:</strong> {analysis.summary}
        {analysis.key_info && <div style={{ marginTop: 5 }}><strong>Key info:</strong> {analysis.key_info}</div>}
      </div>

      {analysis.draft_reply && (
        <div className="draft-section">
          <div className="draft-header">
            <span className="draft-label">Draft reply</span>
            {!isDone && <button className="edit-btn" onClick={() => setEditing(!editing)}>{editing ? "Cancel" : "Edit"}</button>}
          </div>
          {editing
            ? <textarea className="draft-textarea" rows={6} value={draft} onChange={e => setDraft(e.target.value)} />
            : <div className="draft-text">{draft}</div>
          }
        </div>
      )}

      {!isDone && (
        <div className="actions">
          <button className="approve-btn" onClick={handleApprove} disabled={loading || !analysis.draft_reply}>
            {loading ? "Sending…" : "✓ Approve & Send"}
          </button>
          <button className="reject-btn" onClick={handleReject} disabled={loading}>Reject</button>
        </div>
      )}
    </div>
  );
}

export default function App() {
  const [emails, setEmails]       = useState([]);
  const [stats, setStats]         = useState(null);
  const [loading, setLoading]     = useState(true);
  const [running, setRunning]     = useState(false);
  const [filter, setFilter]       = useState("all");
  const [lastSync, setLastSync]   = useState(null);
  const [showCompose, setShowCompose] = useState(false);

  const fetchAll = useCallback(async () => {
    try {
      const [eRes, sRes] = await Promise.all([
        fetch(`${API}/emails`, { headers: HEADERS }),
        fetch(`${API}/stats`,  { headers: HEADERS }),
      ]);
      setEmails((await eRes.json()).emails || []);
      setStats(await sRes.json());
      setLastSync(new Date());
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAll();
    const t = setInterval(fetchAll, 30000);
    return () => clearInterval(t);
  }, [fetchAll]);

  async function triggerRun() {
    setRunning(true);
    await fetch(`${API}/run`, { method: "POST", headers: HEADERS });
    setTimeout(() => { fetchAll(); setRunning(false); }, 5000);
  }

  async function handleApprove(id) {
    await fetch(`${API}/approve/${id}`, { method: "POST", headers: HEADERS });
    fetchAll();
  }

  async function handleReject(id) {
    await fetch(`${API}/reject/${id}`, { method: "POST", headers: HEADERS });
    fetchAll();
  }

  async function handleDraftChange(id, draft) {
    await fetch(`${API}/draft/${id}`, {
      method: "PUT", headers: HEADERS,
      body: JSON.stringify({ draft_reply: draft }),
    });
  }

  const filtered = filter === "all"
    ? emails
    : emails.filter(e => e.status === filter || e.analysis?.category === filter);

  return (
    <>
      <style>{css}</style>

      {showCompose && <ComposeModal onClose={() => setShowCompose(false)} />}

      <div className="topbar">
        <div className="logo"><div className="logo-dot" />Email Agent</div>
        <div style={{ flex: 1 }} />
        {lastSync && <span className="sync-label">SYNCED {lastSync.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>}
        <button className="compose-btn" onClick={() => setShowCompose(true)}>✦ Compose</button>
        <button className="run-btn" onClick={triggerRun} disabled={running}>
          {running ? "Running…" : "⟳ Run Now"}
        </button>
      </div>

      <div className="main">
        {stats && (
          <div className="stats-row">
            <div className="stat-card"><div className="stat-label">Total</div><div className="stat-value">{stats.total}</div></div>
            <div className="stat-card highlight-pending"><div className="stat-label">Pending</div><div className="stat-value">{stats.pending}</div></div>
            <div className="stat-card highlight-sent"><div className="stat-label">Sent</div><div className="stat-value">{stats.sent}</div></div>
            <div className="stat-card highlight-rejected"><div className="stat-label">Rejected</div><div className="stat-value">{stats.rejected}</div></div>
          </div>
        )}

        <div className="filters">
          {["all", "pending", "sent", "rejected", "lead", "client", "support"].map(f => (
            <button key={f} className={`filter-btn ${filter === f ? "active" : ""}`} onClick={() => setFilter(f)}>{f}</button>
          ))}
        </div>

        {loading ? (
          <div className="empty-state"><div className="empty-icon">◌</div><div className="empty-text">Loading emails…</div></div>
        ) : filtered.length === 0 ? (
          <div className="empty-state"><div className="empty-icon">◎</div><div className="empty-text">No emails here · Click Run Now to fetch</div></div>
        ) : (
          filtered.map(item => (
            <EmailCard key={item.email.id} item={item} onApprove={handleApprove} onReject={handleReject} onDraftChange={handleDraftChange} />
          ))
        )}
      </div>
    </>
  );
}
