"""
drive_service.py
----------------
Handles file upload to Supabase Storage.
Replaces Google Drive upload (same interface, drop-in replacement).

Configure in secrets.toml:
  [settings]
  supabase_url = "https://xxxxxxxxxxxx.supabase.co"
  supabase_key = "your-service-role-key"
  supabase_bucket = "submissions"
"""

import io
import streamlit as st
import requests


def build_filename(question_id: str, student_name: str, student_id: str) -> str:
    clean_name = student_name.strip().replace(" ", "_")
    clean_id = student_id.strip().replace(" ", "_")
    return f"{question_id}_{clean_name}_{clean_id}.jpg"


def upload_image(
    image_bytes: bytes,
    question_id: str,
    student_name: str,
    student_id: str,
) -> str:
    """
    Upload image to Supabase Storage.
    Returns the filename on success, raises on failure.
    """
    supabase_url = st.secrets["settings"]["supabase_url"].rstrip("/")
    supabase_key = st.secrets["settings"]["supabase_key"]
    bucket = st.secrets["settings"]["supabase_bucket"]
    filename = build_filename(question_id, student_name, student_id)

    url = f"{supabase_url}/storage/v1/object/{bucket}/{filename}"

    headers = {
        "Authorization": f"Bearer {supabase_key}",
        "Content-Type": "image/jpeg",
    }

    response = requests.put(url, headers=headers, data=image_bytes)

    if response.status_code not in (200, 201):
        raise Exception(f"Supabase upload failed: {response.status_code} {response.text}")

    return filename
