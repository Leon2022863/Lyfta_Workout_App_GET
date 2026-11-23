import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("LYFTA_API_KEY")
BASE_URL = os.getenv("LYFTA_BASE_URL", "https://my.lyfta.app/api/v1").rstrip("/")
DAYS_BACK = int(os.getenv("DEFAULT_DAYS_BACK", "14"))


# ==========================================
# 1. FETCH WORKOUTS FROM LYFTA
# ==========================================
def fetch_recent_workouts(days_back: int = DAYS_BACK) -> list[dict]:
    if not API_KEY:
        raise ValueError("LYFTA_API_KEY is missing. Add it to your local .env file.")

    today_utc = datetime.now(timezone.utc).date()
    from_date = (today_utc - timedelta(days=days_back)).isoformat()
    to_date = today_utc.isoformat()

    headers = {"Authorization": f"Bearer {API_KEY}"}
    url = f"{BASE_URL}/workouts"

    all_workouts = []
    page = 1

    while True:
        params = {
            "from": from_date,
            "to": to_date,
            "limit": 50,
            "page": page,
        }
        response = requests.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        payload = response.json()

        workouts = payload.get("workouts", payload if isinstance(payload, list) else [])
        all_workouts.extend(workouts)

        total_pages = payload.get("total_pages", 1) if isinstance(payload, dict) else 1
        if page >= total_pages:
            break
        page += 1

    return all_workouts


# ==========================================
# 2. FIELD EXTRACTORS & REPORT BUILDER
# ==========================================
def extract_exercise_name(ex: dict) -> str:
    """Finds the actual exercise name regardless of Lyfta's nested or flat schema."""
    # Check common flat keys
    for key in ("exercise_title", "exercise_name", "title", "name", "exerciseTitle", "exerciseName"):
        val = ex.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()

    # Check nested exercise object (e.g., {"exercise": {"title": "Bench Press"}})
    nested = ex.get("exercise") or ex.get("exercise_info") or ex.get("details")
    if isinstance(nested, dict):
        for key in ("title", "name", "exercise_title", "exercise_name"):
            val = nested.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()
    elif isinstance(nested, str) and nested.strip():
        return nested.strip()

    # Fallback: scan any string field with 'name' or 'title' in its key
    for k, v in ex.items():
        if ("name" in k.lower() or "title" in k.lower()) and isinstance(v, str) and v.strip():
            return v.strip()

    return f"Unknown Exercise (keys: {', '.join(ex.keys())})"


def format_set(s: dict) -> str:
    """Formats a single set (weight x reps, bodyweight, or cardio distance/time)."""
    weight = (
        s.get("weight")
        or s.get("weight_lbs")
        or s.get("weight_kg")
        or s.get("load")
    )
    reps = s.get("reps") or s.get("rep_count")
    dist = s.get("distance") or s.get("distance_miles") or s.get("distance_km")
    dur = s.get("duration") or s.get("duration_seconds") or s.get("time")

    if weight is not None and reps is not None:
        return f"{weight}x{reps}"
    if reps is not None:
        return f"BWx{reps}"
    if dist is not None or dur is not None:
        parts = [str(p) for p in (dist, dur) if p is not None]
        return " / ".join(parts)
    return ""


def build_discord_chunks(workouts: list[dict], days_back: int = DAYS_BACK, max_len: int = 1900) -> list[str]:
    """Builds one or more <=1900-char text blocks so every workout and exercise is sent."""
    if not workouts:
        return [f"LYFTA SYNC (Last {days_back} Days)\nNo workouts logged in this window."]

    header = f"LYFTA WORKOUT SYNC (Last {days_back} Days | {len(workouts)} Sessions)\n" + ("=" * 48)
    session_blocks = []

    for w in workouts:
        title = w.get("title") or w.get("name") or w.get("workout_title") or "Workout"
        raw_date = str(
            w.get("date")
            or w.get("workout_date")
            or w.get("start_time")
            or w.get("created_at")
            or ""
        )[:10]

        lines = [f"[{raw_date}] {title}"]
        exercises = w.get("exercises") or w.get("workout_exercises") or []

        for ex in exercises:
            ex_name = extract_exercise_name(ex)
            sets = ex.get("sets") or ex.get("workout_sets") or []
            set_summaries = [formatted for s in sets if (formatted := format_set(s))]

            if set_summaries:
                lines.append(f"  - {ex_name}: {', '.join(set_summaries)}")
            else:
                lines.append(f"  - {ex_name} ({len(sets)} sets)")

        session_blocks.append("\n".join(lines))

    # Pack session blocks into Discord-safe chunks without cutting off exercises
    chunks = []
    current_chunk = header

    for block in session_blocks:
        candidate = f"{current_chunk}\n\n{block}"
        if len(candidate) <= max_len:
            current_chunk = candidate
        else:
            if current_chunk:
                chunks.append(current_chunk)
            # If a single massive workout exceeds max_len on its own, split by line
            if len(block) > max_len:
                sub_lines = block.splitlines()
                sub_chunk = sub_lines[0]
                for line in sub_lines[1:]:
                    if len(sub_chunk) + len(line) + 1 <= max_len:
                        sub_chunk += f"\n{line}"
                    else:
                        chunks.append(sub_chunk)
                        sub_chunk = f"{sub_lines[0]} (cont.)\n{line}"
                current_chunk = sub_chunk
            else:
                current_chunk = block

    if current_chunk:
        chunks.append(current_chunk)

    return chunks


# ==========================================
# 5. NOTIFICATION DISPATCH (DISCORD WEBHOOK)
# ==========================================
def send_discord_webhook(status_text: str):
    """Dispatches the status report securely via Discord HTTPS Webhook."""
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")

    if not webhook_url or "api/webhooks" not in webhook_url:
        print("[*] Discord webhook URL missing or invalid in .env. Skipping remote dispatch.")
        return

    payload = {
        "content": f"```text\n{status_text}\n```"
    }

    try:
        print("[*] Pushing telemetry via HTTPS Webhook...")
        response = requests.post(webhook_url, json=payload, timeout=10)
        response.raise_for_status()
        print("[*] Status report successfully dispatched to Discord channel!")
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Failed to send Discord webhook: {e}", file=sys.stderr)


def main() -> None:
    workouts = fetch_recent_workouts()

    output_dir = Path(__file__).resolve().parent.parent / "data"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"workouts_{datetime.now(timezone.utc).date().isoformat()}.json"

    output_file.write_text(json.dumps(workouts, indent=2), encoding="utf-8")
    print(f"[*] Saved {len(workouts)} workouts to {output_file}")

    chunks = build_discord_chunks(workouts)
    for idx, chunk in enumerate(chunks, start=1):
        print(f"[*] Dispatching Discord message {idx}/{len(chunks)}...")
        send_discord_webhook(chunk)
        if idx < len(chunks):
            time.sleep(1.0)  # Avoid Discord webhook rate limits


if __name__ == "__main__":
    main()