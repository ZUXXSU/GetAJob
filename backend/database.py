import os
from datetime import datetime
from sqlalchemy import (
    create_engine, Column, Integer, String,
    Float, DateTime, Text, Boolean, ForeignKey, text
)
from sqlalchemy.orm import declarative_base, sessionmaker

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'jobs.db')
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

engine = create_engine(
    f'sqlite:///{DB_PATH}',
    connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    source = Column(String(50))
    external_id = Column(String(200))
    title = Column(String(300))
    company = Column(String(200))
    location = Column(String(200))
    salary_min = Column(Float, nullable=True)
    salary_max = Column(Float, nullable=True)
    salary_text = Column(String(200), nullable=True)
    description = Column(Text, nullable=True)
    url = Column(String(500))
    match_score = Column(Integer, default=0)
    found_date = Column(DateTime, default=datetime.utcnow)
    posted_date = Column(DateTime, nullable=True)
    status = Column(String(20), default="new")  # new/saved/applied/rejected
    applied_date = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)
    notified = Column(Boolean, default=False)
    auto_applied = Column(Boolean, default=False)


class ScrapeLog(Base):
    __tablename__ = "scrape_logs"

    id = Column(Integer, primary_key=True)
    source = Column(String(50))
    timestamp = Column(DateTime, default=datetime.utcnow)
    jobs_found = Column(Integer, default=0)
    jobs_new = Column(Integer, default=0)
    error = Column(Text, nullable=True)
    duration_seconds = Column(Float, nullable=True)


class AIAnalysis(Base):
    __tablename__ = "ai_analyses"

    id = Column(Integer, primary_key=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), unique=True)
    ai_score = Column(Integer, nullable=True)
    match_reasons = Column(Text, nullable=True)   # JSON array string
    red_flags = Column(Text, nullable=True)        # JSON array string
    skill_gaps = Column(Text, nullable=True)       # JSON array string
    suggested_salary = Column(String(200), nullable=True)
    apply_recommended = Column(Boolean, nullable=True)
    one_line_summary = Column(Text, nullable=True)
    cover_letter = Column(Text, nullable=True)
    tailored_resume = Column(Text, nullable=True)
    hr_email = Column(String(300), nullable=True)
    interview_prep = Column(Text, nullable=True)
    analyzed_at = Column(DateTime, default=datetime.utcnow)


class Application(Base):
    __tablename__ = "applications"

    id = Column(Integer, primary_key=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), unique=True)
    stage = Column(String(50), default="applied")  # applied/phone_screen/interview/offer/rejected
    hr_email = Column(String(300), nullable=True)
    cover_letter = Column(Text, nullable=True)
    email_sent = Column(Boolean, default=False)
    email_sent_at = Column(DateTime, nullable=True)
    response_received = Column(Boolean, default=False)
    response_date = Column(DateTime, nullable=True)
    next_action = Column(String(300), nullable=True)
    next_action_date = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)
    follow_up_count = Column(Integer, default=0)
    last_follow_up_at = Column(DateTime, nullable=True)
    interview_date = Column(DateTime, nullable=True)
    offer_amount = Column(String(200), nullable=True)
    salary_negotiated = Column(String(200), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ResumeProfile(Base):
    __tablename__ = "resume_profiles"

    id = Column(Integer, primary_key=True)
    name = Column(String(100))                   # e.g. "Flutter Developer", "Full Stack"
    description = Column(String(300), nullable=True)  # short note on what this resume targets
    content = Column(Text)                       # plain text / markdown resume body
    target_roles = Column(Text, nullable=True)   # JSON array: ["flutter","mobile","ios"]
    pdf_path = Column(String(500), nullable=True) # path to uploaded PDF on disk
    is_default = Column(Boolean, default=False)
    updated_at = Column(DateTime, default=datetime.utcnow)


class LinkedInLog(Base):
    __tablename__ = "linkedin_logs"

    id = Column(Integer, primary_key=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=True)
    company = Column(String(200))
    recruiter_name = Column(String(200), nullable=True)
    recruiter_url = Column(String(500), nullable=True)
    message_text = Column(Text, nullable=True)
    message_sent = Column(Boolean, default=False)
    status = Column(String(100), default="pending")
    sent_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class CompanyWatch(Base):
    """Companies to watch — alert when new matching jobs appear."""
    __tablename__ = "company_watches"

    id = Column(Integer, primary_key=True)
    company = Column(String(200))
    role_filter = Column(String(200), nullable=True)
    min_score = Column(Integer, default=50)
    last_alerted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class CodingPractice(Base):
    """Daily coding practice tracker for interview prep."""
    __tablename__ = "coding_practice"

    id = Column(Integer, primary_key=True)
    date = Column(String(10), unique=True)  # YYYY-MM-DD
    topic = Column(String(100))
    problem_title = Column(String(300))
    platform_url = Column(String(500))
    difficulty = Column(String(20))
    completed = Column(Boolean, default=False)
    completed_at = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)


class OutreachLog(Base):
    """Track which outreach templates work best (response rate)."""
    __tablename__ = "outreach_logs"

    id = Column(Integer, primary_key=True)
    template_key = Column(String(100))
    target_company = Column(String(200))
    target_person = Column(String(200), nullable=True)
    channel = Column(String(50))  # linkedin/email/twitter
    message_text = Column(Text)
    sent_at = Column(DateTime, default=datetime.utcnow)
    got_response = Column(Boolean, default=False)
    response_at = Column(DateTime, nullable=True)


class ApplicationLog(Base):
    """Detailed log of every action taken — scrape, analyze, email, LinkedIn, stage change."""
    __tablename__ = "application_logs"

    id = Column(Integer, primary_key=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=True)
    action = Column(String(100))
    detail = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)


def init_db():
    Base.metadata.create_all(bind=engine)
    _migrate()


def _migrate():
    """Add missing columns to existing tables without losing data."""
    migrations = [
        "ALTER TABLE jobs ADD COLUMN auto_applied BOOLEAN DEFAULT 0",
        "ALTER TABLE ai_analyses ADD COLUMN required_experience INTEGER",
        "ALTER TABLE ai_analyses ADD COLUMN experience_qualified BOOLEAN DEFAULT 1",
        "ALTER TABLE ai_analyses ADD COLUMN interview_prep TEXT",
        "ALTER TABLE resume_profiles ADD COLUMN description TEXT",
        "ALTER TABLE resume_profiles ADD COLUMN target_roles TEXT",
        "ALTER TABLE resume_profiles ADD COLUMN pdf_path TEXT",
        "ALTER TABLE resume_profiles ADD COLUMN is_default BOOLEAN DEFAULT 0",
        "ALTER TABLE applications ADD COLUMN follow_up_count INTEGER DEFAULT 0",
        "ALTER TABLE applications ADD COLUMN last_follow_up_at TIMESTAMP",
        "ALTER TABLE applications ADD COLUMN interview_prep TEXT",
        "ALTER TABLE applications ADD COLUMN interview_date TIMESTAMP",
        "ALTER TABLE applications ADD COLUMN offer_amount TEXT",
        "ALTER TABLE applications ADD COLUMN salary_negotiated TEXT",
    ]
    with engine.connect() as conn:
        for stmt in migrations:
            try:
                conn.execute(text(stmt))
                conn.commit()
            except Exception:
                pass  # column already exists


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
