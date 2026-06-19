import { useState, useEffect, useCallback } from "react";
import {
  PieChart, Pie, Cell, Tooltip, ResponsiveContainer,
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
} from "recharts";

const API = "https://email-agent-crxi.onrender.com";

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

const CATEGORY_HEX = {
  lead: "#0ff2b2", client: "#3b82f6", support: "#f59e0b",
  newsletter: "#8b5cf6", spam: "#ef4444", other: "#4b5563",
};

const PRIORITY_DOT = { high: "#ef4444", medium: "#f59e0b", low: "#22c55e" };
const PRIORITY_HEX = { high: "#ef4444", medium: "#f59e0b", low: "#22c55e" };
const SENTIMENT_HEX = { positive: "#0ff2b2", neutral: "#60a5fa", negative: "#ef4444" };

const STATUS_STYLE = {
  pending:  { label: "Pending",  color: "#f59e0b" },
  sent:     { label: "Sent",     color: "#22c55e" },
  rejected: { label: "Rejected", color: "#ef4444" },
};

const TONES = [
  { key: "professional", label: "Professional", icon: "◈" },
  { key: "friendly",     label: "Friendly",     icon: "◉" },
  { key: "concise",      label: "Concise",      icon: "→" },
];

function confidenceStyle(score) {
  const pct = Math.round((score || 0) * 100);
  const color = pct >= 80 ? "#0ff2b2" : pct >= 60 ? "#f59e0b" : "#ef4444";
  return { pct, color };
}

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

  /* ── Tab switcher ── */
  .tab-group { display: flex; gap: 2px; background: #ffffff08; border-radius: 7px; padding: 3px; }
  .tab-btn { padding: 5px 16px; border-radius: 5px; border: none; background: transparent; color: #ffffff40; font-size: 12px; font-family: 'DM Mono', monospace; letter-spacing: 0.06em; cursor: pointer; transition: all 0.15s; }
  .tab-btn.active { background: #ffffff12; color: #fff; }
  .tab-btn:hover:not(.active) { color: #ffffff70; }

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
  .card-from { font-size: 12px; color: #ffffff40; display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
  .priority-dot { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; }
  .badges { display: flex; align-items: center; gap: 6px; margin-left: auto; flex-shrink: 0; }
  .badge { font-family: 'DM Mono', monospace; font-size: 9px; letter-spacing: 0.1em; padding: 3px 8px; border-radius: 4px; text-transform: uppercase; border: 1px solid; }
  .confidence-badge { font-family: 'DM Mono', monospace; font-size: 9px; letter-spacing: 0.08em; padding: 3px 8px; border-radius: 4px; border: 1px solid; display: flex; align-items: center; gap: 4px; }
  .confidence-bar { height: 3px; border-radius: 99px; background: #ffffff10; width: 32px; overflow: hidden; flex-shrink: 0; }
  .confidence-fill { height: 100%; border-radius: 99px; transition: width 0.4s ease; }
  .summary-box { background: #ffffff05; border: 1px solid #ffffff08; border-radius: 8px; padding: 12px 14px; font-size: 12.5px; color: #94a3b8; line-height: 1.65; margin-bottom: 14px; }
  .summary-box strong { color: #cbd5e1; font-weight: 500; }
  .draft-section { margin-bottom: 14px; }
  .draft-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; gap: 8px; flex-wrap: wrap; }
  .draft-label { font-family: 'DM Mono', monospace; font-size: 9px; letter-spacing: 0.15em; color: #ffffff25; text-transform: uppercase; }
  .draft-header-right { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
  .tone-group { display: flex; gap: 4px; }
  .tone-btn { font-size: 10px; padding: 3px 9px; border: 1px solid #ffffff12; border-radius: 4px; background: transparent; color: #ffffff35; cursor: pointer; font-family: 'DM Mono', monospace; letter-spacing: 0.05em; transition: all 0.15s; display: flex; align-items: center; gap-4px; }
  .tone-btn:hover:not(:disabled) { border-color: #ffffff30; color: #ffffff70; }
  .tone-btn.active { border-color: #0ff2b260; color: #0ff2b2; background: #0ff2b210; }
  .tone-btn:disabled { opacity: 0.3; cursor: not-allowed; }
  .tone-spinning { display: inline-block; animation: spin 0.8s linear infinite; }
  @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
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
  .wake-banner { font-family: 'DM Mono', monospace; font-size: 11px; color: #f59e0b; background: #f59e0b10; border: 1px solid #f59e0b30; border-radius: 6px; padding: 6px 12px; margin-right: 4px; }

  /* ── Analytics tab ── */
  .analytics-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-top: 4px; }
  .chart-card { background: #0d1117; border: 1px solid #ffffff0d; border-radius: 12px; padding: 22px 20px; }
  .chart-title { font-family: 'DM Mono', monospace; font-size: 9px; letter-spacing: 0.15em; color: #ffffff30; text-transform: uppercase; margin-bottom: 20px; }
  .chart-card.full-width { grid-column: 1 / -1; }
  .legend-row { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
  .legend-dot { width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; }
  .legend-label { font-family: 'DM Mono', monospace; font-size: 11px; color: #ffffff50; flex: 1; text-transform: capitalize; }
  .legend-value { font-family: 'DM Mono', monospace; font-size: 11px; color: #ffffff80; }
  .legend-bar-bg { flex: 2; height: 3px; background: #ffffff08; border-radius: 99px; overflow: hidden; }
  .legend-bar-fill { height: 100%; border-radius: 99px; }
  .no-data { font-family: 'DM Mono', monospace; font-size: 11px; color: #ffffff20; text-align: center; padding: 40px 0; }
  .analytics-stat-row { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-bottom: 16px; }
  .analytics-stat { background: #ffffff06; border: 1px solid #ffffff0d; border-radius: 10px; padding: 14px 16px; }
  .analytics-stat .stat-label { font-family: 'DM Mono', monospace; font-size: 9px; letter-spacing: 0.15em; color: #ffffff30; margin-bottom: 6px; text-transform: uppercase; }
  .analytics-stat .stat-value { font-family: 'DM Mono', monospace; font-size: 22px; font-weight: 700; color: #fff; }
`;

// ── Custom tooltip for charts ──────────────────────────────────────────────
function CustomTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const { name, value, color } = payload[0];
  return (
    <div style={{ background: "#0d1117", border: "1px solid #ffffff15", borderRadius: 6, padding: "7px 12px", fontFamily: "'DM Mono', monospace", fontSize: 11 }}>
      <span style={{ color: color || "#0ff2b2" }}>{name}</span>
      <span style={{ color: "#ffffff60", marginLeft: 8 }}>{value}</span>
    </div>
  );
}

// ── Analytics Tab ──────────────────────────────────────────────────────────
function AnalyticsTab({ emails, stats }) {
  if (!emails.length) {
    return (
      <div className="empty-state" style={{ marginTop: 24 }}>
        <div className="empty-icon">◎</div>
        <div className="empty-text">No data yet · Run the agent to populate charts</div>
      </div>
    );
  }

  // Build category counts
  const catCounts = {};
  const priCounts = { high: 0, medium: 0, low: 0 };
  const sentCounts = { positive: 0, neutral: 0, negative: 0 };

  emails.forEach(({ analysis }) => {
    const cat = analysis?.category || "other";
    catCounts[cat] = (catCounts[cat] || 0) + 1;
    const pri = analysis?.priority || "low";
    priCounts[pri] = (priCounts[pri] || 0) + 1;
    const sent = analysis?.sentiment || "neutral";
    sentCounts[sent] = (sentCounts[sent] || 0) + 1;
  });

  const catData = Object.entries(catCounts).map(([name, value]) => ({ name, value, color: CATEGORY_HEX[name] || "#4b5563" }));
  const priData = [
    { name: "High",   value: priCounts.high,   color: "#ef4444" },
    { name: "Medium", value: priCounts.medium, color: "#f59e0b" },
    { name: "Low",    value: priCounts.low,    color: "#22c55e" },
  ].filter(d => d.value > 0);
  const sentData = Object.entries(sentCounts)
    .filter(([, v]) => v > 0)
    .map(([name, value]) => ({ name, value, color: SENTIMENT_HEX[name] || "#60a5fa" }));

  const total = emails.length;
  const maxCat = Math.max(...catData.map(d => d.value), 1);

  // Avg confidence
  const avgConf = Math.round(
    emails.reduce((sum, { analysis }) => sum + (analysis?.confidence || 0), 0) / total * 100
  );

  // Action required count
  const actionCount = emails.filter(({ analysis }) => analysis?.action_required).length;

  return (
    <div>
      {/* Top stat strip */}
      <div className="analytics-stat-row">
        <div className="analytics-stat">
          <div className="stat-label">Avg Confidence</div>
          <div className="stat-value" style={{ color: avgConf >= 80 ? "#0ff2b2" : avgConf >= 60 ? "#f59e0b" : "#ef4444" }}>{avgConf}%</div>
        </div>
        <div className="analytics-stat">
          <div className="stat-label">Action Required</div>
          <div className="stat-value" style={{ color: "#f59e0b" }}>{actionCount}</div>
        </div>
        <div className="analytics-stat">
          <div className="stat-label">Leads Found</div>
          <div className="stat-value" style={{ color: "#0ff2b2" }}>{catCounts["lead"] || 0}</div>
        </div>
      </div>

      <div className="analytics-grid">

        {/* Category donut */}
        <div className="chart-card">
          <div className="chart-title">By Category</div>
          <ResponsiveContainer width="100%" height={160}>
            <PieChart>
              <Pie data={catData} cx="50%" cy="50%" innerRadius={45} outerRadius={70} paddingAngle={3} dataKey="value">
                {catData.map((entry, i) => <Cell key={i} fill={entry.color} opacity={0.85} />)}
              </Pie>
              <Tooltip content={<CustomTooltip />} />
            </PieChart>
          </ResponsiveContainer>
          <div style={{ marginTop: 12 }}>
            {catData.map(({ name, value, color }) => (
              <div key={name} className="legend-row">
                <div className="legend-dot" style={{ background: color }} />
                <div className="legend-label">{name}</div>
                <div className="legend-bar-bg">
                  <div className="legend-bar-fill" style={{ width: `${(value / maxCat) * 100}%`, background: color }} />
                </div>
                <div className="legend-value">{value}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Sentiment donut */}
        <div className="chart-card">
          <div className="chart-title">By Sentiment</div>
          <ResponsiveContainer width="100%" height={160}>
            <PieChart>
              <Pie data={sentData} cx="50%" cy="50%" innerRadius={45} outerRadius={70} paddingAngle={3} dataKey="value">
                {sentData.map((entry, i) => <Cell key={i} fill={entry.color} opacity={0.85} />)}
              </Pie>
              <Tooltip content={<CustomTooltip />} />
            </PieChart>
          </ResponsiveContainer>
          <div style={{ marginTop: 12 }}>
            {sentData.map(({ name, value, color }) => (
              <div key={name} className="legend-row">
                <div className="legend-dot" style={{ background: color }} />
                <div className="legend-label">{name}</div>
                <div className="legend-bar-bg">
                  <div className="legend-bar-fill" style={{ width: `${(value / total) * 100}%`, background: color }} />
                </div>
                <div className="legend-value">{value}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Priority bar chart — full width */}
        <div className="chart-card full-width">
          <div className="chart-title">By Priority</div>
          <ResponsiveContainer width="100%" height={120}>
            <BarChart data={priData} margin={{ top: 0, right: 0, bottom: 0, left: -20 }} barSize={32}>
              <CartesianGrid vertical={false} stroke="#ffffff06" />
              <XAxis dataKey="name" tick={{ fontFamily: "'DM Mono', monospace", fontSize: 10, fill: "#ffffff30" }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontFamily: "'DM Mono', monospace", fontSize: 10, fill: "#ffffff20" }} axisLine={false} tickLine={false} allowDecimals={false} />
              <Tooltip content={<CustomTooltip />} cursor={{ fill: "#ffffff05" }} />
              <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                {priData.map((entry, i) => <Cell key={i} fill={entry.color} fillOpacity={0.8} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Status breakdown — full width */}
        {stats && (
          <div className="chart-card full-width">
            <div className="chart-title">Status Breakdown</div>
            <ResponsiveContainer width="100%" height={120}>
              <BarChart
                data={[
                  { name: "Pending",  value: stats.pending,  color: "#f59e0b" },
                  { name: "Sent",     value: stats.sent,     color: "#22c55e" },
                  { name: "Rejected", value: stats.rejected, color: "#ef4444" },
                ]}
                margin={{ top: 0, right: 0, bottom: 0, left: -20 }}
                barSize={32}
              >
                <CartesianGrid vertical={false} stroke="#ffffff06" />
                <XAxis dataKey="name" tick={{ fontFamily: "'DM Mono', monospace", fontSize: 10, fill: "#ffffff30" }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontFamily: "'DM Mono', monospace", fontSize: 10, fill: "#ffffff20" }} axisLine={false} tickLine={false} allowDecimals={false} />
                <Tooltip content={<CustomTooltip />} cursor={{ fill: "#ffffff05" }} />
                <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                  {[{ color: "#f59e0b" }, { color: "#22c55e" }, { color: "#ef4444" }].map((entry, i) => (
                    <Cell key={i} fill={entry.color} fillOpacity={0.8} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}

      </div>
    </div>
  );
}

// ── Compose Modal ──────────────────────────────────────────────────────────
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
      const res = await fetch(`${API}/compose`, { method: "POST", headers: HEADERS, body: JSON.stringify(form) });
      setResult(await res.json());
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  }

  function handleCopy() {
    if (!result) return;
    navigator.clipboard.writeText(`Subject: ${result.subject}\n\n${result.email}`);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <div className="modal-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="modal">
        <div className="modal-title">✦ Compose cold email</div>
        <div className="modal-sub">Powered by LLaMA 3.3 · 80 words · signed as you</div>
        <div className="field"><label>Recipient name</label><input placeholder="e.g. Sarah Chen" value={form.name} onChange={e => setForm({...form, name: e.target.value})} /></div>
        <div className="field"><label>Company</label><input placeholder="e.g. Stripe" value={form.company} onChange={e => setForm({...form, company: e.target.value})} /></div>
        <div className="field"><label>Role you're targeting</label><input placeholder="e.g. AI Engineer Intern" value={form.role} onChange={e => setForm({...form, role: e.target.value})} /></div>
        <div className="field"><label>Extra context (optional)</label><textarea placeholder="e.g. I saw their recent blog post on LLM agents..." value={form.context} onChange={e => setForm({...form, context: e.target.value})} /></div>
        <div className="modal-actions">
          <button className="generate-btn" onClick={handleGenerate} disabled={loading || !form.name || !form.company || !form.role}>{loading ? "Generating…" : "⟳ Generate email"}</button>
          <button className="cancel-btn" onClick={onClose}>Cancel</button>
        </div>
        {result && (
          <div className="result-box">
            <div className="result-subject">SUBJECT: <span>{result.subject}</span></div>
            <div className="result-email">{result.email}</div>
            <button className={`copy-btn ${copied ? "copied" : ""}`} onClick={handleCopy}>{copied ? "✓ Copied!" : "Copy email + subject"}</button>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Email Card ─────────────────────────────────────────────────────────────
function EmailCard({ item, onApprove, onReject, onDraftChange }) {
  const { email, analysis, status } = item;
  const [editing, setEditing]       = useState(false);
  const [draft, setDraft]           = useState(analysis.draft_reply || "");
  const [loading, setLoading]       = useState(false);
  const [activeTone, setActiveTone] = useState(null);
  const [toneLoading, setToneLoading] = useState(false);

  const cat      = analysis.category || "other";
  const pri      = analysis.priority || "low";
  const catStyle = CATEGORY_COLOR[cat] || CATEGORY_COLOR.other;
  const isDone   = status === "sent" || status === "rejected";
  const statusInfo = STATUS_STYLE[status] || STATUS_STYLE.pending;
  const { pct, color: confColor } = confidenceStyle(analysis.confidence);

  async function handleTone(tone) {
    if (toneLoading) return;
    setToneLoading(true); setActiveTone(tone);
    try {
      const res = await fetch(`${API}/tone/${email.id}`, { method: "POST", headers: HEADERS, body: JSON.stringify({ tone }) });
      const data = await res.json();
      if (data.draft_reply) { setDraft(data.draft_reply); setEditing(false); }
    } catch (e) { console.error(e); }
    finally { setToneLoading(false); }
  }

  async function handleApprove() {
    setLoading(true);
    try { if (editing) await onDraftChange(email.id, draft); await onApprove(email.id); setEditing(false); }
    catch (e) { console.error(e); }
    finally { setLoading(false); }
  }

  async function handleReject() {
    setLoading(true);
    try { await onReject(email.id); }
    catch (e) { console.error(e); }
    finally { setLoading(false); }
  }

  return (
    <div className={`email-card ${isDone ? "done" : ""}`}>
      <div className="card-header">
        <div className="cat-icon" style={{ background: catStyle.bg, border: `1px solid ${catStyle.border}20`, color: catStyle.text }}>{CATEGORY_ICONS[cat]}</div>
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
          <span className="confidence-badge" style={{ color: confColor, borderColor: `${confColor}40`, background: `${confColor}10` }} title={`AI confidence: ${pct}%`}>
            <div className="confidence-bar"><div className="confidence-fill" style={{ width: `${pct}%`, background: confColor }} /></div>
            {pct}%
          </span>
          <span className="badge" style={{ color: statusInfo.color, borderColor: `${statusInfo.color}40`, background: `${statusInfo.color}10` }}>{statusInfo.label}</span>
          <span className="date-label">{new Date(email.date).toLocaleDateString("en-GB", { day: "numeric", month: "short" })}</span>
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
            {!isDone && (
              <div className="draft-header-right">
                <div className="tone-group">
                  {TONES.map(t => (
                    <button key={t.key} className={`tone-btn ${activeTone === t.key ? "active" : ""}`} onClick={() => handleTone(t.key)} disabled={toneLoading || loading} title={`Rewrite as ${t.label}`}>
                      {toneLoading && activeTone === t.key ? <span className="tone-spinning">⟳</span> : t.icon} {t.label}
                    </button>
                  ))}
                </div>
                <button className="edit-btn" onClick={() => setEditing(!editing)}>{editing ? "Cancel" : "Edit"}</button>
              </div>
            )}
          </div>
          {editing ? <textarea className="draft-textarea" rows={6} value={draft} onChange={e => setDraft(e.target.value)} /> : <div className="draft-text">{draft}</div>}
        </div>
      )}
      {!isDone && (
        <div className="actions">
          <button className="approve-btn" onClick={handleApprove} disabled={loading || !analysis.draft_reply}>{loading ? "Sending…" : "✓ Approve & Send"}</button>
          <button className="reject-btn" onClick={handleReject} disabled={loading}>Reject</button>
        </div>
      )}
    </div>
  );
}

// ── App ────────────────────────────────────────────────────────────────────
export default function App() {
  const [emails, setEmails]           = useState([]);
  const [stats, setStats]             = useState(null);
  const [loading, setLoading]         = useState(true);
  const [running, setRunning]         = useState(false);
  const [waking, setWaking]           = useState(false);
  const [filter, setFilter]           = useState("all");
  const [lastSync, setLastSync]       = useState(null);
  const [showCompose, setShowCompose] = useState(false);
  const [activeTab, setActiveTab]     = useState("inbox"); // "inbox" | "analytics"

  const fetchAll = useCallback(async () => {
    try {
      const [eRes, sRes] = await Promise.all([
        fetch(`${API}/emails`, { headers: HEADERS }),
        fetch(`${API}/stats`,  { headers: HEADERS }),
      ]);
      setEmails((await eRes.json()).emails || []);
      setStats(await sRes.json());
      setLastSync(new Date());
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => {
    fetchAll();
    const t = setInterval(fetchAll, 10000);
    return () => clearInterval(t);
  }, [fetchAll]);

  async function triggerRun() {
    setRunning(true); setWaking(true);
    const controller = new AbortController();
    const hardTimeout = setTimeout(() => controller.abort(), 60000);
    try {
      await fetch(`${API}/run`, { method: "POST", headers: HEADERS, signal: controller.signal });
    } catch (e) { console.error("Run request failed or timed out:", e); }
    finally { clearTimeout(hardTimeout); setWaking(false); }
    let attempts = 0;
    const poll = setInterval(async () => {
      await fetchAll();
      attempts++;
      if (attempts >= 10) { clearInterval(poll); setRunning(false); }
    }, 3000);
  }

  async function handleApprove(id) { await fetch(`${API}/approve/${id}`, { method: "POST", headers: HEADERS }); fetchAll(); }
  async function handleReject(id)  { await fetch(`${API}/reject/${id}`,  { method: "POST", headers: HEADERS }); fetchAll(); }
  async function handleDraftChange(id, draft) {
    await fetch(`${API}/draft/${id}`, { method: "PUT", headers: HEADERS, body: JSON.stringify({ draft_reply: draft }) });
  }

  const filtered = filter === "all" ? emails : emails.filter(e => e.status === filter || e.analysis?.category === filter);

  return (
    <>
      <style>{css}</style>
      {showCompose && <ComposeModal onClose={() => setShowCompose(false)} />}

      <div className="topbar">
        <div className="logo"><div className="logo-dot" />Email Agent</div>
        <div style={{ marginLeft: 16 }}>
          <div className="tab-group">
            <button className={`tab-btn ${activeTab === "inbox" ? "active" : ""}`} onClick={() => setActiveTab("inbox")}>INBOX</button>
            <button className={`tab-btn ${activeTab === "analytics" ? "active" : ""}`} onClick={() => setActiveTab("analytics")}>ANALYTICS</button>
          </div>
        </div>
        <div style={{ flex: 1 }} />
        {lastSync && <span className="sync-label">SYNCED {lastSync.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>}
        {waking && <span className="wake-banner">Waking up server…</span>}
        <button className="compose-btn" onClick={() => setShowCompose(true)}>✦ Compose</button>
        <button className="run-btn" onClick={triggerRun} disabled={running}>{running ? "Running…" : "⟳ Run Now"}</button>
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

        {activeTab === "inbox" ? (
          <>
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
          </>
        ) : (
          <AnalyticsTab emails={emails} stats={stats} />
        )}
      </div>
    </>
  );
}
