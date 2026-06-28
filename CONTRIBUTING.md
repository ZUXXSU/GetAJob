# Contributing to GetAJob

Thanks for your interest!

## Quick start for contributors

```bash
git clone https://github.com/ZUXXSU/GetAJob.git
cd GetAJob
bash setup.sh
cp .env.example .env  # fill in dummy values for testing
```

## Code style

- Python: PEP 8, type hints where useful
- No comments unless explaining a non-obvious "why"
- Function names should make their purpose obvious
- Each module < 400 lines — split if longer

## Adding a new scraper

1. Create `backend/scrapers/your_source.py`
2. Inherit from `BaseScraper`, implement `fetch_jobs(query, location)`
3. Return list of dicts with keys: `source, external_id, title, company, location, salary_min, salary_max, salary_text, description, url, posted_date`
4. Register in `backend/scheduler.py` `SCRAPERS` list + `_SCRAPER_QUERIES` dict
5. Test live: `python -c "from scrapers.your_source import YourScraper; print(YourScraper().safe_fetch('test'))"`

## Adding a new AI feature (uses Gemini CLI)

1. Add function to `backend/gemini.py` or new module
2. Use `_run(prompt, timeout=30)` — handles subprocess, noise filtering
3. Always provide a fallback if Gemini returns empty
4. For JSON responses, use `_parse_json()` helper

## Adding a new notification channel

1. Create `backend/<channel>_notifier.py`
2. Implement `<channel>_available()` and `send_<channel>(msg)` functions
3. Plug into `backend/telegram_notifier.py` `send()` to multi-cast

## Adding a REST endpoint

1. Add to `backend/api.py` under appropriate section
2. Use Pydantic models for request bodies
3. Use `db: Session = Depends(get_db)` for DB access
4. Return JSON dict, not Pydantic objects (simpler)

## Testing

There's no formal test suite. Before submitting:

```bash
# Syntax check
python -m compileall backend/ -q

# Boot smoke test
cd backend && python main.py &
sleep 5
curl http://localhost:8000/api/health
kill $!
```

## PR checklist

- [ ] No personal data added (check with `grep -ri "your_name\|your_email" backend/`)
- [ ] `.env` not committed
- [ ] `python -m compileall backend/ -q` passes
- [ ] New endpoints documented in README
- [ ] If you added a scrape source, tested live with `safe_fetch()`

## What we'd love help with

- More scrapers (Indeed India, Foundit, Hirect, AngelList Talent)
- Browser extension for one-click ATS form fill
- Local LLM support (Ollama) as Gemini alternative
- iOS/Android companion app
- Better resume PDF parser (current uses pypdf — sometimes mangles complex layouts)
- More mock interview scenarios

## What NOT to add

- External AI API integrations (defeats the local-AI design)
- Telemetry/analytics that phone home
- Required cloud services
- Features that require breaking ToS of job boards

## Code of conduct

Be respectful. Help newcomers. Disagree on technical merits, not personality.
