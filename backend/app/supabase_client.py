"""Supabase client — cloud sync. Keys from backend/.env. Falls back to local-only."""
import os

def get_client():
    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_ANON_KEY", "")
    if not url.startswith("http") or not key or key.startswith("paste-"):
        return None
    from supabase import create_client
    return create_client(url, key)
