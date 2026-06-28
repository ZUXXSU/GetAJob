# GetAJob — Autonomous Enterprise Job Search Platform

> Self-hosted, AI-powered job hunting that runs autonomously for months.
> Built to **find, score, apply, follow up, and coach** — without you driving every step.

**49 backend modules · 97 REST endpoints · 7 job scrapers · 9 cron jobs · 4 notification channels · 7-tab dashboard**

![Stack](https://img.shields.io/badge/Stack-FastAPI%20%2B%20SQLite%20%2B%20Gemini%20CLI-blue)
![License](https://img.shields.io/badge/License-MIT-green)
![Status](https://img.shields.io/badge/Status-Production-success)

---

## What It Does

| Stage | What runs automatically |
|---|---|
| **Discover** | 7 scrapers (Adzuna, JSearch, Naukri, LinkedIn, Remotive, RemoteOK, RSS) every 12h, with fuzzy dedup, blacklist filter, and visa-aware accessibility check |
| **Decide** | Gemini CLI scores every job (0–100), parses experience requirements, flags red flags, recommends apply/skip |
| **Act** | Auto-applies to high-match jobs: picks the best resume PDF for the role, generates a tailored cover letter, finds the HR email, sends Gmail with **only the PDF attached** (resume text never leaks into the body) |
| **Outreach** | Sends LinkedIn recruiter messages via Playwright, 5 proven cold-outreach templates, reference letter generator |
| **Track** | Kanban pipeline, IMAP reply detection every 2h, activity heatmap, funnel analytics, full action log |
| **Improve** | Mock interviewer chat, mock recruiter screening, ATS keyword check, skill-gap coach, salary intelligence, daily coding problem |
| **Direct** | Daily Playbook (timed 2-hr routine), Success Predictor (probability % + top 5 actions to raise it) |
| **Persist** | 9 cron jobs, weekly Monday performance email, weekly backups, Telegram + WhatsApp + Slack + email digest |

---

## Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                       FastAPI Backend (port 8000)                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐ │
│  │ 7 Scrapers│  │ Gemini  │  │ Scheduler │  │  Email   │  │ Database │ │
│  │           │  │   CLI   │  │ (9 jobs)  │  │  (SMTP)  │  │ (SQLite) │ │
│  └─────┬────┘  └────┬────┘  └─────┬────┘  └────┬────┘  └─────┬───┘ │
│        │            │             │            │             │       │
│  ┌─────┴────────────┴─────────────┴────────────┴─────────────┴────┐  │
│  │              97 REST API Endpoints                              │  │
│  └────────────────────────────┬───────────────────────────────────┘  │
└─────────────────────────────────┼──────────────────────────────────────┘
                                  │
                  ┌───────────────┴───────────────┐
                  │                                │
          ┌───────▼───────┐               ┌────────▼────────┐
          │ 7-Tab SPA UI  │               │  Notifications  │
          │   (Tailwind)  │               │ Email/Telegram  │
          │  localhost:80 │               │ WhatsApp/Slack  │
          └───────────────┘               └─────────────────┘
```

---

## Quick Start

```bash
git clone https://github.com/ZUXXSU/GetAJob.git
cd GetAJob

# 1. Setup
bash setup.sh         # creates venv, installs deps

# 2. Configure
cp .env.example .env
nano .env             # fill in CANDIDATE_*, SMTP_*, Gemini path

# 3. Drop your resume PDF
mkdir -p data/resumes
cp /path/to/your_resume.pdf data/resumes/default.pdf

# 4. Run
bash run.sh           # http://localhost:8000

# OR install as macOS LaunchAgent (auto-restart, runs on boot)
bash install_service.sh
```

**Prerequisites:**
- Python 3.10+
- [Gemini CLI](https://github.com/google-gemini/gemini-cli) (`npm install -g @google/gemini-cli`)
- Gmail account with [App Password](https://myaccount.google.com/apppasswords) (for SMTP)

---

## Key Features

### 🤖 AI-Powered (via Gemini CLI — no API keys needed)

- **Job analysis** — fit score, red flags, skill gaps, salary advice, apply/skip recommendation
- **Cover letter generator** — 3-paragraph personalized letters per job
- **Resume tailoring** — reorders bullets, injects job-specific keywords
- **Resume picker** — when you upload multiple resumes, Gemini selects the best one per job
- **Mock interview** — multi-turn technical chat with feedback
- **Mock recruiter call** — practice the 15-min screening with 8 standard questions
- **Skill coach** — aggregates gaps across all jobs → 30-day learning roadmap
- **Salary intelligence** — market percentiles + negotiation strategy
- **Career coach chat** — open-ended advice with full context of your state

### 📨 Email Automation

- Daily digest of 60+ score jobs (9 AM IST)
- Auto-apply emails with **PDF attachment only** (resume text never inlined)
- Follow-up emails at 7 + 14 days (max 2 per application)
- Thank-you email auto-triggered when stage moves to "interview"
- Weekly Monday performance report (Gemini-written motivational summary)
- IMAP scanner detects replies every 2h → updates pipeline + alerts you

### 🎯 Tracking & Analytics

- Kanban pipeline: Applied → Phone Screen → Interview → Offer → Rejected
- 9-stage funnel: Scraped → Score 60+ → Score 80+ → AI Analyzed → AI Recommended → Applied → Phone Screen → Interview → Offer
- 60-day activity heatmap (GitHub-style)
- Weekly application goal with progress bar
- Per-source job distribution, score distribution
- Full chronological action log

### 🏆 Habit Engineering

- 18 achievement badges across 6 levels (Rookie → Master)
- Daily coding practice tracker with streak counter
- Daily Playbook: timed 2-hour routine with specific tasks
- Success Predictor: live probability % + top 5 actions to raise it

### 🛂 Job Filters

- Experience requirement parser (skips jobs needing 5yr if you have 1.5yr)
- Visa accessibility classifier (blocks US-only / requires-sponsorship roles)
- Cross-source deduplication (fuzzy title+company match)
- Company + keyword blacklist (from `.env`)

### 🌐 Notifications

| Channel | Setup |
|---|---|
| Email | Gmail App Password |
| Telegram | `@BotFather` → `/newbot` → set token + chat_id |
| WhatsApp | Twilio Sandbox (1000 free msgs/month) |
| Slack | Incoming Webhook URL |

All four broadcast in parallel — set up any combination.

### 💼 Application Toolkit

- **Outreach templates** — 5 proven cold messages (LinkedIn recruiter, engineer, HR email, InMail short, warm referral) with Gemini personalization
- **Form autofill kit** — 26-field JSON for any ATS, plus browser bookmarklet
- **Reference letter generator** — request letters from past managers
- **Calendar export (.ics)** — subscribe to interview + follow-up reminders in any calendar app
- **Offer comparator** — score multiple offers, Gemini picks the winner
- **Negotiation simulator** — practice salary negotiation with Gemini playing the manager

### 🔧 Operations

- Health monitor: 10 subsystems checked (DB, Gemini, SMTP, IMAP, scrapers, scheduler, Telegram, LinkedIn session, resume PDFs, disk)
- Onboarding wizard: tracks 8 setup steps
- Auto-backup every Sunday (tar.gz of DB + resumes, keeps last 10)
- Cleanup job removes stale low-score jobs after 60 days
- All errors caught per-scraper — one failing source never kills the others

---

## Configuration (`.env`)

Everything personal lives in one file. **No hardcoded names, emails, companies, or skills in the codebase.** Anyone can fork this and configure for their own search.

### Required
```bash
CANDIDATE_NAME=Your Full Name
CANDIDATE_EMAIL=you@example.com
CANDIDATE_PHONE=+91 9999999999
CANDIDATE_LOCATION=Your City, Country
CANDIDATE_SKILLS=python,react,node,sql
CANDIDATE_TARGET_ROLES=software engineer,full stack developer
CANDIDATE_SEARCH_QUERIES=software engineer,backend developer
SMTP_EMAIL=you@gmail.com
SMTP_PASSWORD=xxxx xxxx xxxx xxxx     # Gmail App Password
DEFAULT_RESUME_PDF=/path/to/your_resume.pdf
GEMINI_BIN=/usr/local/bin/gemini
```

### Optional (each unlocks more features)
```bash
ADZUNA_APP_ID, ADZUNA_APP_KEY    # 1000 free req/month
RAPIDAPI_KEY                       # JSearch BASIC plan
HUNTER_API_KEY                     # HR email finder
LINKEDIN_EMAIL, LINKEDIN_PASSWORD  # recruiter messaging
TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
TWILIO_*                           # WhatsApp via Twilio
SLACK_WEBHOOK_URL                  # Slack alerts
AUTO_APPLY_ENABLED=true            # off by default; sends real emails
```

See [`.env.example`](.env.example) for the complete list.

---

## REST API (97 endpoints)

| Category | Examples |
|---|---|
| Jobs | `GET /api/jobs`, `GET /api/qualified-jobs`, `GET /api/accessible-jobs`, `GET /api/jobs/{id}` |
| AI | `POST /api/jobs/{id}/analyze`, `POST /api/jobs/{id}/cover-letter`, `POST /api/jobs/{id}/tailor-resume`, `POST /api/jobs/{id}/ats-check`, `POST /api/jobs/{id}/interview-prep` |
| Batch | `POST /api/analyze/all`, `GET /api/analyze/progress` |
| Resumes | `GET/POST /api/resumes`, `POST /api/resumes/{id}/upload-pdf`, `POST /api/resumes/select-for-job/{id}` |
| Pipeline | `GET/POST /api/applications`, `PUT /api/applications/{id}` |
| Outreach | `GET /api/outreach/templates`, `POST /api/outreach/personalize`, `POST /api/jobs/{id}/linkedin-message` |
| Follow-ups | `GET /api/followups/due`, `POST /api/followups/run` |
| Coach | `POST /api/coach/chat`, `GET /api/skill-coach/analysis`, `POST /api/mock-interview/start`, `POST /api/recruiter-call/start`, `GET /api/coding/daily` |
| Predict | `GET /api/success-predictor`, `GET /api/playbook/today`, `GET /api/recommendations/daily` |
| Analytics | `GET /api/analytics`, `GET /api/analytics/funnel`, `GET /api/heatmap`, `GET /api/salary-intel` |
| Offers | `POST /api/offers/save`, `POST /api/offers/compare`, `POST /api/negotiation/start` |
| Achievements | `GET /api/achievements`, `GET /api/goals` |
| System | `GET /api/health`, `GET /api/onboarding`, `POST /api/backup/create`, `GET /api/backup/list` |
| Export | `GET /api/export/jobs.csv`, `GET /api/export/applications.csv`, `GET /api/calendar.ics` |

Full Swagger docs: `http://localhost:8000/docs`

---

## Tech Stack

- **Backend**: FastAPI · SQLAlchemy · SQLite · APScheduler · pypdf · BeautifulSoup
- **Scraping**: requests · Playwright (LinkedIn)
- **AI**: Gemini CLI (subprocess) — no API keys, all local
- **Email**: smtplib · IMAP (Gmail)
- **Frontend**: Single HTML + Tailwind CDN + vanilla JS (no build step)
- **Storage**: SQLite for everything — no Postgres/Redis/Mongo
- **Notifications**: Email + Telegram Bot API + Twilio (WhatsApp) + Slack Webhooks

---

## File Structure

```
GetAJob/
├── .env.example         # Config template (real .env gitignored)
├── .gitignore
├── README.md            # This file
├── requirements.txt
├── setup.sh             # First-time setup
├── run.sh               # Start server
├── install_service.sh   # macOS LaunchAgent installer
├── uninstall_service.sh
├── data/                # Runtime (gitignored)
│   ├── jobs.db          # SQLite database
│   ├── resumes/         # Uploaded resume PDFs
│   ├── linkedin_session/ # Playwright session
│   ├── backups/         # Weekly tar.gz backups
│   └── getajob.log
├── backend/
│   ├── main.py          # FastAPI app
│   ├── api.py           # 97 REST endpoints
│   ├── config.py        # .env parser
│   ├── database.py      # 10 SQLAlchemy models
│   ├── scheduler.py     # 9 cron jobs
│   ├── gemini.py        # Gemini CLI wrapper
│   ├── matcher.py       # Rule-based scoring
│   ├── auto_apply.py    # Apply engine (PDF-only attachment)
│   ├── ... 40 more modules
│   └── scrapers/        # adzuna, jsearch, naukri, linkedin,
│                        # remotive, remoteok, rss_jobs
└── frontend/
    └── index.html       # 7-tab SPA
```

---

## Scheduled Jobs (Asia/Kolkata TZ)

| Job | Schedule | What it does |
|---|---|---|
| `scrape` | every 12h | Fetch from 7 sources |
| `digest` | daily 9 AM | Email top jobs |
| `morning_apply` | Mon–Fri 9 AM | Auto-apply at optimal HR-reading time |
| `auto_apply` | every 24h | Standard auto-apply cycle |
| `followups` | daily 10 AM | Send 7d + 14d follow-ups |
| `reply_check` | every 2h | IMAP scan for recruiter replies |
| `weekly_report` | Mon 8 AM | Performance email |
| `cleanup` | Sun 3 AM | Remove stale jobs |
| `backup` | Sun 4 AM | tar.gz backup of DB + resumes |

---

## Privacy & Security

- **All personal data lives in `.env`** (gitignored). Nothing hardcoded in code.
- **No external AI APIs** — Gemini runs locally via the CLI.
- **Resume PDF binary only in emails** — text content never appears in any outgoing message.
- **LinkedIn credentials** stay local in Playwright session storage.
- **Gmail App Password**, not your main password.
- **Auto-apply OFF by default** — must explicitly set `AUTO_APPLY_ENABLED=true`.

---

## Disclaimer

- For personal use only.
- Respect rate limits and ToS of every scraped source.
- LinkedIn automation may violate ToS — use at your own discretion.
- Always **test with `dry_run=true`** before enabling live auto-apply.
- This tool **does not guarantee** employment. It maximizes the probability of getting interviews by automating the mechanical parts of the search so you can focus on interviewing well.

---

## License

MIT — fork it, customize it, use it for your own job search.

---

## Contributing

PRs welcome. Areas to improve:
- More job source scrapers (Indeed India, Foundit, Hirect, AngelList)
- Browser extension for one-click apply
- Offline mode (local LLM via Ollama)
- iOS/Android companion app

Open an issue first to discuss large changes.
