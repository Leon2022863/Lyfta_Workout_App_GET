```markdown
# 🏋️‍♂️ Lyfta Workout Sync

A lightweight Python utility to fetch your recent workout logs from the [Lyfta Personal API](https://my.lyfta.app/community/api), save local JSON backups, and dispatch a formatted summary report to a Discord channel via webhook.

## ✨ Features
- 📅 Automatically calculates the date window based on `DEFAULT_DAYS_BACK` (defaults to the last 14 days).
- 🔄 Handles multi-page API responses automatically.
- 💬 Formats workout sessions (dates, exercises, weights, and reps) into a clean text block within Discord's 2,000-character limit and dispatches it via HTTPS webhook.
- 🔒 Keeps API keys, webhook URLs, and personal workout exports out of Git via `.gitignore`.

## 📂 Project Structure
```text
lyfta-workout-sync/
├── .env                  # Local secrets & webhook URL (ignored by git)
├── .env.example          # Environment variable template
├── .gitignore            # Excludes .env, virtual environments, and data exports
├── requirements.txt      # Python dependencies
├── README.md             # Project documentation
├── src/
│   └── fetch_workouts.py # Fetches workouts, saves JSON, and sends Discord webhook
└── data/                 # Exported JSON logs (ignored by git)
    └── .gitkeep

```

## 📋 Prerequisites

* 🐍 Python 3.10+
* 🔑 A Lyfta account with a personal API key generated at `https://my.lyfta.app/community/api`
* 🔔 *(Optional)* A Discord channel webhook URL (`Server Settings > Integrations > Webhooks`) for remote notifications

## ⚙️ Setup

1. **Clone the repository**
```bash
git clone [https://github.com/](https://github.com/)<your-username>/lyfta-workout-sync.git
cd lyfta-workout-sync

```


2. **Create and activate a virtual environment**
* **macOS / Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate

```


* **Windows (PowerShell):**
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1

```




3. **Install dependencies**
```bash
pip install -r requirements.txt

```


4. **Configure environment variables**
Copy `.env.example` to `.env` and fill in your credentials:
```bash
cp .env.example .env

```


```env
LYFTA_API_KEY=your_actual_lyfta_api_key
LYFTA_BASE_URL=[https://my.lyfta.app/api/v1](https://my.lyfta.app/api/v1)
DEFAULT_DAYS_BACK=14
DISCORD_WEBHOOK_URL=[https://discord.com/api/webhooks/your_webhook_id/your_webhook_token](https://discord.com/api/webhooks/your_webhook_id/your_webhook_token)

```


*(If `DISCORD_WEBHOOK_URL` is left blank or omitted, the script will still save the local JSON file and skip the Discord dispatch.)*

## 🚀 Usage

Run the sync script from the project root:

```bash
python src/fetch_workouts.py

```

* 💾 **Local Output:** Saves full raw JSON logs to `data/workouts_YYYY-MM-DD.json`.
* 📨 **Discord Dispatch:** Posts a formatted summary of your recent workouts to your configured Discord channel.

## 🛡️ Security Notes

* 🚫 Never commit your `.env` file or share your `LYFTA_API_KEY` or `DISCORD_WEBHOOK_URL` in public repositories or chats.
* 🔄 If your Lyfta API key is ever exposed, generate a new key on Lyfta's `/community/api` page to immediately revoke the old one.
* 🗑️ If your Discord webhook URL is ever exposed, delete it in your Discord channel's **Integrations > Webhooks** settings and create a new one.

```

```