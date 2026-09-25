# 🎯 Job Hunter Agent

AI-powered job discovery, scoring, and application automation.

## Features

- **8 Job Source Scrapers**: Greenhouse, Lever, Ashby, LinkedIn, Indeed, RemoteOK, Wellfound, WeWorkRemotely
- **AI Match Scoring**: Gemini-powered evaluation of job fit against your resume/profile
- **Telegram Bot**: Real-time notifications with inline Apply/Skip/Details/Cover Letter buttons
- **Deduplication**: SHA256 fingerprinting prevents duplicate job alerts
- **CLI Dashboard**: Rich terminal UI for stats, profile viewing, and manual scrape triggers

## Quick Start

### 1. Install Dependencies

```bash
cd job-hunter
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
playwright install chromium
```

### 2. Configure

```bash
cp .env.example .env
```

Edit `.env` with your API keys:
- **`GEMINI_API_KEY`**: Get from [Google AI Studio](https://aistudio.google.com/apikey)
- **`TELEGRAM_BOT_TOKEN`**: Create a bot via [@BotFather](https://t.me/BotFather)
- **`TELEGRAM_CHAT_ID`**: Send `/start` to your bot, then use [@userinfobot](https://t.me/userinfobot) to find your chat ID

### 3. Set Up Your Profile

Edit `profile.yaml` with your real info — skills, target titles, experience, salary expectations.

### 4. Run

```bash
# Full agent: scrape → score → notify via Telegram
python -m job_hunter run

# One-time scrape (no bot)
python -m job_hunter scrape

# View stats
python -m job_hunter stats

# View profile
python -m job_hunter profile
```

## Architecture

```
job_hunter/
├── scrapers/          # 8 platform scrapers (Playwright + httpx)
│   ├── greenhouse.py  # Direct JSON API
│   ├── lever.py       # Direct JSON API
│   ├── ashby.py       # GraphQL API
│   ├── remoteok.py    # JSON API
│   ├── weworkremotely.py  # HTML scraping
│   ├── wellfound.py   # Playwright browser automation
│   ├── linkedin.py    # Playwright browser automation
│   └── indeed.py      # Playwright browser automation
├── ai/
│   └── scorer.py      # Gemini AI match scoring + cover letter generation
├── bot/
│   └── telegram_bot.py  # Telegram notification bot with inline actions
├── db/
│   └── database.py    # Async SQLite persistence layer
├── models.py          # Pydantic v2 data models
├── config.py          # Settings from .env
├── profile.py         # YAML profile loader
├── engine.py          # Main orchestration engine
└── __main__.py        # CLI entry point
```

## Telegram Bot Commands

| Command | Description |
|:--------|:------------|
| `/start` | Welcome message |
| `/stats` | Show job discovery statistics |
| `/top` | Show top 10 matching jobs |
| `/search <keyword>` | Trigger immediate scrape |
| `/profile` | Show current profile |
| `/help` | List all commands |

## How It Works

1. **Scrape**: All 8 scrapers run concurrently, fetching jobs from APIs and web pages
2. **Deduplicate**: New jobs are fingerprinted and stored in SQLite (duplicates skipped)
3. **Score**: Gemini AI evaluates each job against your profile (0-100 match score)
4. **Notify**: Jobs scoring ≥70 are sent to your Telegram with rich cards
5. **Act**: Tap `✅ Apply` to approve or `📝 Cover Letter` to generate a tailored letter

## License

MIT
# job-hunter
# job-hunter
