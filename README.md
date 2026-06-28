# GetAJob — Enterprise Autonomous Job Search

Fully autonomous job-finding and auto-applying service. Runs 24/7 for months without any AI/LLM assistance from the operator. Uses Gemini CLI (local) for all AI features.

## What it does

1. **Scrapes 6 sources** every 12 hours: Adzuna, JSearch, Naukri, LinkedIn, Remotive, RemoteOK
2. **Scores every job** 0–100 based on skills, role, location, salary, experience requirements
3. **AI analyzes** every job with Gemini — fit score, red flags, skill gaps, salary advice
4. **Generates tailored cover letters + resumes** per job via Gemini
5. **Auto-applies** to high-score matches — picks best resume PDF, generates cover letter, finds HR email, sends Gmail with attachment
6. **Sends LinkedIn messages** to recruiters at target companies via Playwright
7. **Tracks application pipeline** — Applied → Phone Screen → Interview → Offer
8. **Sends follow-up emails** automatically at 7 and 14 days with no response
9. **Triggers thank-you emails** automatically when stage moves to "interview"
10. **Generates interview prep** — Q&A, company research, salary negotiation tips
11. **Provides mock interview practice** with Gemini chatbot
12. **Tracks salary market data** with percentile analysis
13. **Suggests daily top 3** jobs to apply to (Gemini-curated)
14. **Detects re-apply opportunities** when companies post new roles after rejection
15. **Generates reference letter requests** for previous managers
16. **Tracks weekly application goals** with progress bars
17. **Sends weekly Monday reports** by email + Telegram daily summaries
18. **Aggregates skill gaps** from all jobs → 30-day learning roadmap from Gemini

## Quick start

```bash
cd /Volumes/KRYPTIX/test2/GetAJob

# First-time setup
bash setup.sh

# Edit .env (add your keys — see Configuration below)
nano .env

# Run server
bash run.sh

# OR — install as macOS LaunchAgent (auto-restart, runs on boot)
bash install_service.sh
```

Open **http://localhost:8000**

## Configuration (.env)

### Personal Profile
```bash
CANDIDATE_NAME=Your Full Name
CANDIDATE_EMAIL=you@example.com
CANDIDATE_PHONE=+91 9999999999
CANDIDATE_LINKEDIN=linkedin.com/in/your-handle
CANDIDATE_GITHUB=github.com/your-handle
CANDIDATE_LOCATION=Your City, State, Country
CANDIDATE_LOCATION_TARGETS=city1,city2,city3
CANDIDATE_ACCEPT_REMOTE=true
CANDIDATE_MIN_SALARY_INR=500000
CANDIDATE_EXP_YEARS=1.5
CANDIDATE_SKILLS=python,javascript,react,node,...
CANDIDATE_TARGET_ROLES=software engineer,backend developer,...
CANDIDATE_SEARCH_QUERIES=software engineer,full stack developer,...
DEFAULT_RESUME_PDF=/absolute/path/to/your_resume.pdf
```

Drop your resume PDF into `data/resumes/default.pdf` OR set `DEFAULT_RESUME_PDF` to any absolute path.

### Email (Gmail App Password required)
```bash
SMTP_EMAIL=you@gmail.com
SMTP_PASSWORD=abcd efgh ijkl mnop   # 16-char Gmail App Password
NOTIFY_EMAIL=you@gmail.com
```

Get app password: https://myaccount.google.com/apppasswords

### Job APIs (optional — system works without these)
```bash
ADZUNA_APP_ID=...        # https://developer.adzuna.com (free 1000/month)
ADZUNA_APP_KEY=...
RAPIDAPI_KEY=...         # https://rapidapi.com (JSearch BASIC plan)
HUNTER_API_KEY=          # https://hunter.io/api (HR email finder)
```

### Auto-Apply (OFF by default)
```bash
AUTO_APPLY_ENABLED=false        # change to true when ready
AUTO_APPLY_MIN_SCORE=85         # only auto-apply to jobs scoring this high
AUTO_APPLY_INTERVAL_HOURS=24
```

### LinkedIn Automation
```bash
LINKEDIN_EMAIL=you@gmail.com
LINKEDIN_PASSWORD=your_password
```

### Telegram Notifications
```bash
TELEGRAM_BOT_TOKEN=...           # @BotFather → /newbot
TELEGRAM_CHAT_ID=...             # GET /api/telegram/get-chat-id?token=<token>
```

### Filters
```bash
BLACKLIST_COMPANIES=         # comma-separated companies to skip
BLACKLIST_KEYWORDS=unpaid,commission only,mlm
WEEKLY_APPLY_GOAL=10
```

### Gemini CLI
```bash
GEMINI_BIN=/usr/local/bin/gemini    # path to gemini binary
```

## Scheduled Jobs (cron, IST timezone)

| Job | Schedule | Description |
|---|---|---|
| `scrape` | every 12h | Fetch from all 6 sources |
| `digest` | daily 9 AM | Email digest of new 60+ score jobs |
| `morning_apply` | Mon–Fri 9 AM | Optimal-time auto-apply cycle |
| `auto_apply` | every 24h | Standard auto-apply cycle |
| `followups` | daily 10 AM | Send 7d + 14d follow-up emails |
| `weekly_report` | Mon 8 AM | Weekly performance email |
| `cleanup` | Sun 3 AM | Remove stale low-score jobs |

## Dashboard (7 tabs)

1. **Dashboard** — Stats, top matches, AI-analyzed jobs, weekly goal, exports
2. **Jobs** — Browse/filter all jobs, AI analysis, auto-apply per-job
3. **Pipeline** — Kanban: Applied → Phone Screen → Interview → Offer → Rejected
4. **Resumes** — Manage multiple resume PDFs, Gemini extracts text on upload
5. **Follow-ups** — Due follow-ups list with one-click send
6. **Coach** — Daily top 3, mock interview, skill coach, salary intel, heatmap, outreach, re-apply, reference letters
7. **Analytics** — Funnel, sources, score distribution, scrape logs, Telegram setup

## REST API (30+ endpoints)

```
GET  /api/stats                       — dashboard counters
GET  /api/jobs                        — list jobs with filters
GET  /api/qualified-jobs              — jobs matching experience
POST /api/analyze/all                 — batch Gemini analysis (parallel)
GET  /api/analyze/progress            — batch progress poll
POST /api/jobs/{id}/analyze           — analyze one job
POST /api/jobs/{id}/cover-letter      — generate cover letter
POST /api/jobs/{id}/tailor-resume     — tailor resume for job
POST /api/jobs/{id}/ats-check         — ATS keyword analysis
POST /api/jobs/{id}/interview-prep    — Gemini Q&A + research + salary
POST /api/jobs/{id}/auto-apply        — apply (dry_run or live)
POST /api/jobs/{id}/linkedin-message  — send LinkedIn message
GET  /api/resumes                     — list resumes
POST /api/resumes                     — create resume
POST /api/resumes/{id}/upload-pdf     — upload + auto-extract
POST /api/resumes/upload-new          — upload PDF → new resume
POST /api/resumes/select-for-job/{id} — Gemini picks best resume
GET  /api/applications                — list applications
PUT  /api/applications/{id}           — update (auto thank-you on interview)
GET  /api/followups/due               — overdue follow-ups
POST /api/followups/run               — send all due follow-ups
GET  /api/analytics                   — by-source/score/status
GET  /api/analytics/funnel            — 9-stage funnel
GET  /api/heatmap                     — 60-day activity calendar
GET  /api/salary-intel                — market percentiles + advice
GET  /api/recommendations/daily       — Gemini top 3 today
GET  /api/network/outreach            — weekly outreach plan
GET  /api/reapply/candidates          — re-apply suggestions
GET  /api/skill-coach/analysis        — skill gaps + roadmap
POST /api/mock-interview/start        — start mock interview
POST /api/mock-interview/continue     — continue conversation
POST /api/mock-interview/feedback     — final feedback
POST /api/reference-letter/generate   — draft reference request
GET  /api/goals                       — weekly application goal status
GET  /api/export/jobs.csv             — CSV download
GET  /api/export/applications.csv     — CSV download
POST /api/scrape                      — trigger scrape now
POST /api/digest                      — send digest now
POST /api/weekly-report/send          — send weekly report now
POST /api/telegram/test               — test telegram bot
GET  /api/activity                    — full chronological log
GET  /api/logs                        — scrape logs
```

## Tech Stack

- **Backend**: FastAPI + SQLAlchemy + SQLite + APScheduler
- **AI**: Gemini CLI (no Claude, no API keys for AI)
- **Scraping**: requests + BeautifulSoup, Playwright (LinkedIn)
- **Email**: Gmail SMTP (app password)
- **Notifications**: Email + Telegram bot
- **Frontend**: Single HTML + Tailwind CDN + vanilla JS
- **Storage**: SQLite for everything (no Postgres/Redis needed)

## Privacy

- All personal data in `.env` (never hardcoded)
- All processing local (no external API for AI)
- Resume **text never appears in any outgoing email** — PDF binary attachment only
- LinkedIn session stored locally in `data/linkedin_session/`
- No analytics or tracking

## Files

```
GetAJob/
  .env                  — all config (gitignored)
  README.md             — this file
  setup.sh              — first-time setup
  run.sh                — start server
  install_service.sh    — macOS LaunchAgent installer
  uninstall_service.sh  — remove LaunchAgent
  data/resumes/default.pdf — default resume (gitignored — supply your own)
  data/
    jobs.db             — SQLite DB
    resumes/            — uploaded resume PDFs
    linkedin_session/   — Playwright LinkedIn session
    getajob.log         — server log
    service.log         — LaunchAgent stdout
  backend/
    main.py             — FastAPI app
    api.py              — 30+ REST endpoints
    config.py           — .env parser
    database.py         — 7 SQLAlchemy models
    matcher.py          — rule-based scoring
    gemini.py           — Gemini CLI wrapper
    scheduler.py        — 7 cron jobs
    notifier.py         — daily digest emails
    auto_apply.py       — apply engine (PDF-only attachment)
    contact_finder.py   — HR email lookup
    linkedin_messenger.py — LinkedIn Playwright automation
    pdf_extractor.py    — pypdf + Gemini structuring
    experience_filter.py — years-required parser
    deduplicator.py     — cross-source dedup (fuzzy match)
    followup.py         — 7d + 14d follow-up emails
    thankyou.py         — auto thank-you after interview
    interview_prep.py   — Q&A + research + salary
    mock_interview.py   — multi-turn chat with Gemini
    reference_letter.py — reference letter generator
    skill_coach.py      — skill gap aggregation
    salary_intel.py     — market salary percentiles
    heatmap.py          — daily activity tracker
    network_outreach.py — networking suggestions
    reapply_detector.py — re-apply candidates
    recommender.py      — daily top 3 + cleanup
    ats_optimizer.py    — ATS keyword analysis
    weekly_report.py    — Monday performance email
    exporter.py         — CSV export
    telegram_notifier.py — Telegram alerts
    scrapers/
      adzuna.py, jsearch.py, naukri.py,
      linkedin.py, remotive.py, remoteok.py
  frontend/
    index.html          — 7-tab SPA, Tailwind, vanilla JS
```

## Maintenance

Tail logs:
```bash
tail -f data/getajob.log
tail -f data/service.log   # if installed as service
```

Stop service:
```bash
launchctl unload ~/Library/LaunchAgents/com.getajob.plist
```

Restart service:
```bash
launchctl unload ~/Library/LaunchAgents/com.getajob.plist
launchctl load ~/Library/LaunchAgents/com.getajob.plist
```

Database backup:
```bash
cp data/jobs.db data/jobs.db.bak
```

## Disclaimer

For personal use only. Respect rate limits of all scraped sources. LinkedIn automation may violate ToS — use at your own risk. Always review auto-generated cover letters before live send. Test with `dry_run=true` first.
