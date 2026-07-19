"""
AI Email Automation Agent — Streamlit edition
Replaces the FastAPI server + React dashboard with a single Streamlit app.
Reuses backend/agent.py untouched for all IMAP/Groq/SQLite logic.

Author: Ayush Singh Tomar
"""

import sys
import os
import streamlit as st

# Make backend/ importable (agent.py lives there)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

# Bridge Streamlit Cloud secrets -> environment variables, since agent.py
# reads config via os.environ / python-dotenv. Locally, a backend/.env file
# still works fine because load_dotenv() runs inside agent.py.
if hasattr(st, "secrets"):
    for _key in (
        "GROQ_API_KEY", "GMAIL_ADDRESS", "GMAIL_APP_PASS",
        "YOUR_NAME", "YOUR_ROLE", "DB_FILE", "GMAIL_ACCOUNTS",
        "SLACK_WEBHOOK", "SLACK_ALERT_PRIORITIES", "SLACK_ALERT_CATEGORIES",
    ):
        if _key in st.secrets:
            os.environ[_key] = str(st.secrets[_key])

import agent  # noqa: E402

st.set_page_config(page_title="Email Agent", page_icon="📧", layout="wide")

CATEGORY_ICONS = {"lead": "↗", "client": "◈", "support": "⚙", "newsletter": "≡", "spam": "✕", "other": "◉"}
PRIORITY_COLOR = {"high": "🔴", "medium": "🟡", "low": "🟢"}
STATUS_COLOR = {"pending": "🟠 Pending", "sent": "🟢 Sent", "rejected": "🔴 Rejected"}
TONES = ["professional", "friendly", "concise"]

# ── One-time init per session ────────────────────────────────────────────────
if "initialized" not in st.session_state:
    agent.init_db()
    agent.load_all_from_db()
    st.session_state.initialized = True

# ── Sidebar: Run + Compose ───────────────────────────────────────────────────
with st.sidebar:
    st.title("📧 Email Agent")
    st.caption("FastAPI logic, now inside Streamlit")

    if st.button("⟳ Run Now", type="primary", use_container_width=True):
        with st.spinner("Fetching + analyzing unread emails..."):
            agent.run_agent_cycle()
        st.success("Cycle complete.")
        st.rerun()

    st.divider()
    st.subheader("Cycle health")
    cs = agent.CYCLE_STATS
    st.metric("Total cycles", cs["total_cycles"])
    st.metric("Total errors", cs["total_errors"])
    if cs["last_run"]:
        st.caption(f"Last run: {cs['last_run']}")
    if cs["errors_last_cycle"]:
        with st.expander(f"⚠️ {len(cs['errors_last_cycle'])} error(s) last cycle"):
            for e in cs["errors_last_cycle"]:
                st.error(e)

    st.divider()
    with st.expander("✦ Compose cold email"):
        c_name = st.text_input("Recipient name")
        c_company = st.text_input("Company")
        c_role = st.text_input("Role you're targeting")
        c_context = st.text_area("Extra context (optional)")
        if st.button("Generate email", use_container_width=True):
            if not (c_name and c_company and c_role):
                st.warning("Fill in name, company, and role.")
            else:
                with st.spinner("Generating..."):
                    prompt = f"""Write a short, personalized cold email from {agent.YOUR_NAME} ({agent.YOUR_ROLE}) to {c_name} at {c_company} for a {c_role} position.

Additional context: {c_context if c_context else 'None'}

Rules:
- Max 80 words
- Sound human, not robotic
- Mention something specific about reaching out for this role
- End with a soft CTA like 'Would love to connect'
- Sign off as {agent.YOUR_NAME}
- Return ONLY a JSON object with two keys: "subject" and "body"
- No markdown, no backticks, just raw JSON"""
                    import json as _json
                    try:
                        result = agent.groq_client.chat.completions.create(
                            model=agent.GROQ_MODEL, messages=[{"role": "user", "content": prompt}]
                        )
                        raw = result.choices[0].message.content.strip()
                        raw = raw.replace("```json", "").replace("```", "").strip()
                        parsed = _json.loads(raw)
                        st.session_state.compose_result = parsed
                    except Exception as e:
                        st.error(f"Failed: {e}")
        if "compose_result" in st.session_state:
            r = st.session_state.compose_result
            st.text_input("Subject", value=r.get("subject", ""), key="compose_subject", disabled=True)
            st.text_area("Body", value=r.get("body", ""), key="compose_body", height=150, disabled=True)

# ── Stats row ─────────────────────────────────────────────────────────────────
stats = agent.get_db_stats()
c1, c2, c3, c4 = st.columns(4)
c1.metric("Total", stats["total"])
c2.metric("Pending", stats["pending"])
c3.metric("Sent", stats["sent"])
c4.metric("Rejected", stats["rejected"])

st.divider()

# ── Filters ───────────────────────────────────────────────────────────────────
tab_inbox, tab_analytics = st.tabs(["📥 Inbox", "📊 Analytics"])

with tab_inbox:
    filter_choice = st.radio(
        "Filter",
        ["all", "pending", "sent", "rejected", "lead", "client", "support"],
        horizontal=True,
        label_visibility="collapsed",
    )

    items = list(agent.PROCESSED.values())
    priority_order = {"high": 0, "medium": 1, "low": 2}
    items.sort(key=lambda x: priority_order.get(x["analysis"].get("priority", "low"), 2))

    if filter_choice != "all":
        items = [i for i in items if i["status"] == filter_choice or i["analysis"].get("category") == filter_choice]

    if not items:
        st.info("No emails here. Click **Run Now** in the sidebar to fetch unread mail.")
    else:
        for item in items:
            email = item["email"]
            analysis = item["analysis"]
            eid = email["id"]
            status = item["status"]
            cat = analysis.get("category", "other")
            pri = analysis.get("priority", "low")
            is_done = status in ("sent", "rejected")

            icon = CATEGORY_ICONS.get(cat, "◉")
            header = f"{icon} **{email['subject']}**  ·  {PRIORITY_COLOR.get(pri,'')} {pri}  ·  {STATUS_COLOR.get(status, status)}"

            with st.expander(header, expanded=not is_done):
                st.caption(f"From: {email['from']}  ·  {email.get('date','')}")
                st.markdown(f"**Category:** {cat} &nbsp;&nbsp; **Sentiment:** {analysis.get('sentiment','')} &nbsp;&nbsp; **Confidence:** {int(float(analysis.get('confidence',0))*100)}%")

                st.markdown("**Summary:**")
                st.write(analysis.get("summary", ""))
                if analysis.get("key_info"):
                    st.markdown(f"**Key info:** {analysis['key_info']}")

                if analysis.get("draft_reply"):
                    st.markdown("**Draft reply:**")
                    draft_key = f"draft_{eid}"
                    draft_text = st.text_area(
                        "Draft", value=analysis["draft_reply"], key=draft_key,
                        height=140, label_visibility="collapsed", disabled=is_done,
                    )

                    if not is_done:
                        tone_cols = st.columns(3)
                        for i, tone in enumerate(TONES):
                            if tone_cols[i].button(f"↻ {tone.capitalize()}", key=f"tone_{tone}_{eid}"):
                                with st.spinner(f"Rewriting as {tone}..."):
                                    new_draft = agent.regenerate_draft(eid, tone)
                                if new_draft:
                                    st.rerun()

                        col_approve, col_reject = st.columns([3, 1])
                        if col_approve.button("✓ Approve & Send", key=f"approve_{eid}", type="primary", use_container_width=True):
                            if draft_text != analysis["draft_reply"]:
                                agent.PROCESSED[eid]["analysis"]["draft_reply"] = draft_text
                                agent.update_db_draft(eid, draft_text)
                            with st.spinner("Sending..."):
                                ok = agent.send_approved_reply(eid)
                            if ok:
                                st.success("Sent!")
                                st.rerun()
                            else:
                                st.error("Send failed — check logs / cycle health.")
                        if col_reject.button("✕ Reject", key=f"reject_{eid}", use_container_width=True):
                            agent.PROCESSED[eid]["status"] = "rejected"
                            agent.update_db_status(eid, "rejected")
                            st.rerun()
                else:
                    st.caption("No draft generated (likely spam/newsletter).")

with tab_analytics:
    items = list(agent.PROCESSED.values())
    if not items:
        st.info("No data yet. Run the agent to populate analytics.")
    else:
        cat_counts, pri_counts, sent_counts = {}, {"high": 0, "medium": 0, "low": 0}, {"positive": 0, "neutral": 0, "negative": 0}
        for it in items:
            a = it["analysis"]
            cat_counts[a.get("category", "other")] = cat_counts.get(a.get("category", "other"), 0) + 1
            pri_counts[a.get("priority", "low")] = pri_counts.get(a.get("priority", "low"), 0) + 1
            sent_counts[a.get("sentiment", "neutral")] = sent_counts.get(a.get("sentiment", "neutral"), 0) + 1

        avg_conf = sum(float(it["analysis"].get("confidence", 0)) for it in items) / len(items) * 100
        action_count = sum(1 for it in items if it["analysis"].get("action_required"))

        m1, m2, m3 = st.columns(3)
        m1.metric("Avg Confidence", f"{avg_conf:.0f}%")
        m2.metric("Action Required", action_count)
        m3.metric("Leads Found", cat_counts.get("lead", 0))

        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown("**By Category**")
            st.bar_chart(cat_counts)
        with col_b:
            st.markdown("**By Priority**")
            st.bar_chart(pri_counts)

        st.markdown("**By Sentiment**")
        st.bar_chart(sent_counts)

        st.markdown("**Status Breakdown**")
        st.bar_chart({"pending": stats["pending"], "sent": stats["sent"], "rejected": stats["rejected"]})