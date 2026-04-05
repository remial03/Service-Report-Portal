import os
import json
from datetime import datetime, timezone

import requests
from werkzeug.security import generate_password_hash

USERS_FILE = os.path.join(os.path.dirname(__file__), "..", "users.json")
SUBMISSIONS_FILE = os.path.join(os.path.dirname(__file__), "..", "submissions.json")


def read_users() -> list:
    if not os.path.exists(USERS_FILE):
        return []
    with open(USERS_FILE, "r") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []


def write_users(users: list) -> None:
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=4)


def sync_monday_users() -> int:
    """Fetch Monday.com users and add any that don't already exist.
    Returns the number of new users added, or -1 on failure.
    Called automatically at app startup.
    """
    api_key = os.getenv("MONDAY_API_KEY", "")
    default_pw = os.getenv("DEFAULT_USER_PASSWORD", "")
    if not api_key or not default_pw:
        return 0  # Silently skip if not configured
    try:
        resp = requests.post(
            "https://api.monday.com/v2",
            json={"query": "{ users { id name email } }"},
            headers={"Authorization": api_key, "Content-Type": "application/json"},
            timeout=15,
        )
        resp.raise_for_status()
        monday_users = resp.json().get("data", {}).get("users", [])
    except Exception as e:
        print(f"[startup sync] Failed to fetch Monday.com users: {e}")
        return -1

    users = read_users()
    existing = {u.get("username") for u in users}
    hashed_pw = generate_password_hash(default_pw)
    added = 0
    for mu in monday_users:
        email = (mu.get("email") or "").strip().lower()
        if not email or email in existing:
            continue
        users.append({
            "username": email, "email": email,
            "name": mu.get("name") or email,
            "monday_id": str(mu.get("id", "")),
            "provider": "password",
            "password": hashed_pw,
        })
        existing.add(email)
        added += 1
    if added:
        write_users(users)
        print(f"[startup sync] Added {added} new users from Monday.com.")
    return added


# ── Submission log ────────────────────────────────────────────────────────────

def log_submission(username: str, item_name: str, item_id: str) -> None:
    """Append a submission record to submissions.json."""
    try:
        entries = []
        if os.path.exists(SUBMISSIONS_FILE):
            with open(SUBMISSIONS_FILE, "r") as f:
                try:
                    entries = json.load(f)
                except (json.JSONDecodeError, ValueError):
                    entries = []

        entries.append({
            "username": username,
            "name": item_name,
            "item_id": item_id,
            "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        })

        # Keep last 500 entries total
        if len(entries) > 500:
            entries = entries[-500:]

        with open(SUBMISSIONS_FILE, "w") as f:
            json.dump(entries, f, indent=2)
    except Exception as e:
        print(f"[log_submission] Error: {e}")


def get_user_submissions(username: str, limit: int = 20) -> list:
    """Return the most recent submissions for a given username."""
    if not os.path.exists(SUBMISSIONS_FILE):
        return []
    try:
        with open(SUBMISSIONS_FILE, "r") as f:
            entries = json.load(f)
        user_entries = [e for e in entries if e.get("username") == username]
        return list(reversed(user_entries[-limit:]))
    except (json.JSONDecodeError, ValueError, OSError):
        return []
