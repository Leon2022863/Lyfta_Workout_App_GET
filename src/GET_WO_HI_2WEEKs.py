import json
import os
import sys
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
# 2. FORMAT TELEMETRY REPORT
# ==========================================
def format_workout_report(workouts: list[dict], days_back: int = DAYS_BACK) -> str:
    """Formats workout data into a concise text block under Discord's 2000-char limit."""
    if not workouts:
        return f"LYFTA SYNC (Last {days_back} Days)\nNo workouts logged in this window."

    lines = [f"LYFTA WORKOUT SYNC (Last {days_back} Days | {len(workouts)} Sessions)", "=" * 48]

    for w in workouts:
        title = w.get("title") or w.get("name") or "Workout"
        raw_date = str(w.get("date") or w.get("start_time") or w.get("created_at") or "")[:10]
        lines.append(f"\n[{raw_date}] {title}")

        for ex in w.get("exercises", []):
            ex_name = ex.get("title") or ex.get("name") or "Exercise"
            sets = ex.get("sets", [])
            set_summaries = []
            for s in sets:
                weight = s.get("weight") or s.get("weight_lbs") or s.get("weight_kg")
                reps = s.get("reps")
                dist = s.get("distance")
                dur = s.get("duration")

                if weight is not None and reps is not None:
                    set_summaries.append(f"{weight}x{reps}")
                elif reps is not None:
                    set_summaries.append(f"BWx{reps}")
                elif dist is not None or dur is not None:
                    set_summaries.append(f"{dist or ''}/{dur or ''}".strip("/"))

            if set_summaries:
                lines.append(f"  - {ex_name}: {', '.join(set_summaries)}")
            else:
                lines.append(f"  - {ex_name} ({len(sets)} sets)")

    report = "\n".join(lines)

    # Discord enforces a strict 2000-character limit on 'content' (including ```text\n...\n```)
    max_len = 1900
    if len(report) > max_len:
        report = report[:max_len] + "\n... [truncated — see local JSON for full log]"

    return report


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

    report = format_workout_report(workouts)
    send_discord_webhook(report)


if __name__ == "__main__":
    main()