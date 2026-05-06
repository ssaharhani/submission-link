"""
admin_view.py
-------------
The instructor's control panel.
"""

import streamlit as st
from services import sheets_service


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
    current_q_id = state["question_id"]

    st.subheader("1 · Set the Question ID")
    new_q_id = st.text_input(
        label="Question ID",
        value=current_q_id,
        placeholder="e.g. Q1, Bonus_Q2, Midterm_Q3",
        help="This becomes the prefix in every uploaded filename.",
    )

    st.markdown("---")

    st.subheader("2 · Open or Close Submissions")
    is_open = current_status == "Open"
    col1, col2 = st.columns([1, 2])

    with col1:
        if is_open:
            if st.button("🔴  CLOSE submissions", use_container_width=True):
                _save_state("Closed", new_q_id)
                st.rerun()
        else:
            if st.button("🟢  OPEN submissions", use_container_width=True):
                _save_state("Open", new_q_id)
                st.rerun()

    with col2:
        if is_open:
            st.success(f"**Status: OPEN** — accepting submissions for `{current_q_id}`")
        else:
            st.warning(f"**Status: CLOSED** — submissions are disabled")

    st.markdown("---")

    st.subheader("3 · Save Question ID without toggling")
    if st.button("💾  Save Question ID", use_container_width=False):
        _save_state(current_status, new_q_id)
        st.success(f"Saved! Question ID is now `{new_q_id}` (status unchanged).")
        st.rerun()

    st.markdown("---")

    st.subheader("4 · View submitted files")
    supabase_url = st.secrets["settings"].get("supabase_url", "")
    bucket = st.secrets["settings"].get("supabase_bucket", "submissions")
    if supabase_url:
        storage_url = f"{supabase_url}/project/default/storage/buckets/{bucket}"
        st.markdown(f"[📂 Open Supabase Storage]({storage_url})")
    else:
        st.info("Set `supabase_url` in secrets.toml to see this link.")


def _save_state(status: str, question_id: str) -> None:
    try:
        sheets_service.set_session_state(status, question_id)
    except Exception as e:
        st.error(f"⚠️ Could not save to Google Sheets: {e}")
        st.stop()
