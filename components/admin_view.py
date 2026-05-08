"""
admin_view.py
-------------
Instructor control panel.
Displays the session code prominently when open so teacher can write it on the board.
"""

import time
import streamlit as st
from services import sheets_service

AUTO_CLOSE_MINUTES = 15


def render() -> None:
    st.title("📋 Instructor Control Panel")
    st.markdown("---")

    try:
        sheets_service.ensure_header_row()
    except Exception as e:
        st.error(f"⚠️ Could not connect to Google Sheets: {e}")
        st.stop()

    try:
        state = sheets_service.get_session_state()
    except Exception as e:
        st.error(f"⚠️ Could not read session state: {e}")
        st.stop()

    current_status = state["status"]
    current_q_id   = state["question_id"]
    opened_at      = state.get("opened_at", 0)
    session_code   = state.get("code", "")
    is_open        = current_status == "Open"

    # ── Session code display (shown prominently when open) ────────────────────
    if is_open and session_code:
        st.markdown("## 🔑 Session Code — write this on the board:")
        st.markdown(
            f"<div style='font-size:96px; font-weight:900; letter-spacing:24px; text-align:center'>{session_code}</div>",
            unsafe_allow_html=True,
        )
        st.markdown("---")

    # ── Question ID ───────────────────────────────────────────────────────────
    st.subheader("1 · Set the Question ID")
    new_q_id = st.text_input(
        label="Question ID",
        value=current_q_id,
        placeholder="e.g. Q1, Bonus_Q2, Midterm_Q3",
        help="Hit 'Save Question ID' below to apply without toggling status.",
    )

    st.markdown("---")

    # ── Status toggle ─────────────────────────────────────────────────────────
    st.subheader("2 · Open or Close Submissions")

    col1, col2 = st.columns([1, 2])
    with col1:
        if is_open:
            if st.button("🔴  CLOSE submissions", use_container_width=True):
                sheets_service.set_session_state("Closed", current_q_id)
                st.rerun()
        else:
            if st.button("🟢  OPEN submissions", use_container_width=True):
                sheets_service.set_session_state("Open", new_q_id)
                st.rerun()

    with col2:
        if is_open and opened_at:
            elapsed   = (time.time() - opened_at) / 60
            remaining = max(0.0, AUTO_CLOSE_MINUTES - elapsed)
            mins = int(remaining)
            secs = int((remaining - mins) * 60)
            st.success(f"**OPEN** — `{current_q_id}` — closes in ~**{mins}m {secs}s**")
        elif is_open:
            st.success(f"**Status: OPEN** — `{current_q_id}`")
        else:
            st.warning("**Status: CLOSED** — submissions are disabled")

    if st.button("🔄 Refresh status"):
        st.rerun()

    st.markdown("---")

    # ── Save question ID ──────────────────────────────────────────────────────
    st.subheader("3 · Save Question ID without toggling")
    st.caption("Updates the Question ID while keeping the current Open/Closed status.")
    if st.button("💾  Save Question ID"):
        sheets_service.set_session_state(current_status, new_q_id)
        st.success(f"Saved — Question ID is now `{new_q_id}`")
        st.rerun()

    st.markdown("---")

    # ── Supabase link ─────────────────────────────────────────────────────────
    st.subheader("4 · View submitted files")
    supabase_url = st.secrets["settings"].get("supabase_url", "")
    bucket       = st.secrets["settings"].get("supabase_bucket", "submissions")
    if supabase_url:
        project_id  = supabase_url.replace("https://", "").split(".")[0]
        storage_url = f"https://supabase.com/dashboard/project/{project_id}/storage/buckets/{bucket}"
        st.markdown(f"[📦 Open Supabase Storage]({storage_url})")
