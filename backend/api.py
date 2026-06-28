import json
import logging
import os
import re
import shutil
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import desc
from sqlalchemy.orm import Session

from database import AIAnalysis, Application, ApplicationLog, Job, LinkedInLog, ResumeProfile, ScrapeLog, get_db

_RESUMES_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "resumes")
os.makedirs(_RESUMES_DIR, exist_ok=True)

router = APIRouter(prefix="/api")
logger = logging.getLogger(__name__)


# ── Pydantic models ───────────────────────────────────────────────────────────
class StatusUpdate(BaseModel):
    status: str

class NotesUpdate(BaseModel):
    notes: str

class StageUpdate(BaseModel):
    stage: str

class ApplicationUpdate(BaseModel):
    stage: Optional[str] = None
    notes: Optional[str] = None
    next_action: Optional[str] = None
    next_action_date: Optional[str] = None
    response_received: Optional[bool] = None

class ResumeUpdate(BaseModel):
    content: str

class ResumeCreate(BaseModel):
    name: str
    description: Optional[str] = None
    content: str
    target_roles: Optional[list] = None
    is_default: bool = False

class ResumeEdit(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    content: Optional[str] = None
    target_roles: Optional[list] = None
    is_default: Optional[bool] = None


# ── Jobs ──────────────────────────────────────────────────────────────────────
@router.get("/jobs")
def list_jobs(
    status: Optional[str] = None,
    source: Optional[str] = None,
    min_score: int = 0,
    max_score: int = 100,
    location_filter: Optional[str] = None,
    has_ai: Optional[bool] = None,
    skip: int = 0,
    limit: int = 50,
    sort: str = "score",
    db: Session = Depends(get_db),
):
    q = db.query(Job).filter(Job.match_score >= min_score, Job.match_score <= max_score)
    if status:
        q = q.filter(Job.status == status)
    if source:
        q = q.filter(Job.source == source)
    if location_filter:
        q = q.filter(Job.location.ilike(f"%{location_filter}%"))
    if has_ai is True:
        analyzed_ids = [a.job_id for a in db.query(AIAnalysis.job_id).all()]
        q = q.filter(Job.id.in_(analyzed_ids))
    if has_ai is False:
        analyzed_ids = [a.job_id for a in db.query(AIAnalysis.job_id).all()]
        q = q.filter(Job.id.notin_(analyzed_ids))

    if sort == "date":
        q = q.order_by(desc(Job.found_date))
    elif sort == "ai_score":
        q = q.order_by(desc(Job.match_score))
    else:
        q = q.order_by(desc(Job.match_score), desc(Job.found_date))

    total = q.count()
    jobs = q.offset(skip).limit(limit).all()

    # Attach AI analyses
    job_ids = [j.id for j in jobs]
    analyses = {a.job_id: a for a in db.query(AIAnalysis).filter(AIAnalysis.job_id.in_(job_ids)).all()}

    return {
        "total": total,
        "jobs": [_job_dict(j, analyses.get(j.id)) for j in jobs],
    }


@router.get("/jobs/{job_id}")
def get_job(job_id: int, db: Session = Depends(get_db)):
    j = db.query(Job).filter(Job.id == job_id).first()
    if not j:
        raise HTTPException(404, "Not found")
    analysis = db.query(AIAnalysis).filter_by(job_id=job_id).first()
    app = db.query(Application).filter_by(job_id=job_id).first()
    d = _job_dict(j, analysis, full=True)
    if app:
        d["application"] = _app_dict(app)
    return d


@router.put("/jobs/{job_id}/status")
def update_status(job_id: int, body: StatusUpdate, db: Session = Depends(get_db)):
    j = db.query(Job).filter(Job.id == job_id).first()
    if not j:
        raise HTTPException(404, "Not found")
    j.status = body.status
    if body.status == "applied":
        j.applied_date = datetime.utcnow()
    db.commit()
    return {"ok": True}


@router.put("/jobs/{job_id}/notes")
def update_notes(job_id: int, body: NotesUpdate, db: Session = Depends(get_db)):
    j = db.query(Job).filter(Job.id == job_id).first()
    if not j:
        raise HTTPException(404, "Not found")
    j.notes = body.notes
    db.commit()
    return {"ok": True}


# ── AI endpoints ──────────────────────────────────────────────────────────────
@router.post("/jobs/{job_id}/analyze")
def analyze_job(job_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    j = db.query(Job).filter(Job.id == job_id).first()
    if not j:
        raise HTTPException(404, "Not found")
    existing = db.query(AIAnalysis).filter_by(job_id=job_id).first()
    if existing:
        return {"ok": True, "cached": True, "analysis": _analysis_dict(existing)}
    background_tasks.add_task(_run_analysis, job_id)
    return {"ok": True, "cached": False, "message": "Analysis started — refresh in 30s"}


@router.post("/jobs/{job_id}/cover-letter")
def cover_letter(job_id: int, db: Session = Depends(get_db)):
    j = db.query(Job).filter(Job.id == job_id).first()
    if not j:
        raise HTTPException(404, "Not found")
    analysis = db.query(AIAnalysis).filter_by(job_id=job_id).first()
    if analysis and analysis.cover_letter:
        return {"ok": True, "cached": True, "cover_letter": analysis.cover_letter}
    from gemini import generate_cover_letter
    cl = generate_cover_letter(j.title, j.company, j.description or "")
    if not cl:
        raise HTTPException(500, "Gemini failed to generate cover letter")
    if not analysis:
        analysis = AIAnalysis(job_id=job_id, cover_letter=cl)
        db.add(analysis)
    else:
        analysis.cover_letter = cl
    db.commit()
    return {"ok": True, "cached": False, "cover_letter": cl}


@router.post("/jobs/{job_id}/tailor-resume")
def tailor_resume(job_id: int, db: Session = Depends(get_db)):
    j = db.query(Job).filter(Job.id == job_id).first()
    if not j:
        raise HTTPException(404, "Not found")
    analysis = db.query(AIAnalysis).filter_by(job_id=job_id).first()
    if analysis and analysis.tailored_resume:
        return {"ok": True, "cached": True, "tailored_resume": analysis.tailored_resume}
    resume = db.query(ResumeProfile).filter_by(name="default").first()
    if not resume:
        raise HTTPException(400, "No resume saved. Go to Resume tab and save your resume first.")
    from gemini import tailor_resume as gemini_tailor
    tailored = gemini_tailor(resume.content, j.title, j.company, j.description or "")
    if not analysis:
        analysis = AIAnalysis(job_id=job_id, tailored_resume=tailored)
        db.add(analysis)
    else:
        analysis.tailored_resume = tailored
    db.commit()
    return {"ok": True, "tailored_resume": tailored}


@router.post("/jobs/{job_id}/auto-apply")
def auto_apply_job(job_id: int, dry_run: bool = True, db: Session = Depends(get_db)):
    j = db.query(Job).filter(Job.id == job_id).first()
    if not j:
        raise HTTPException(404, "Not found")
    from auto_apply import _apply_to_job
    result = _apply_to_job(j, db, dry_run=dry_run)
    return {"ok": True, "result": result, "dry_run": dry_run}


# ── Applications pipeline ─────────────────────────────────────────────────────
@router.get("/applications")
def list_applications(stage: Optional[str] = None, db: Session = Depends(get_db)):
    q = db.query(Application)
    if stage:
        q = q.filter(Application.stage == stage)
    apps = q.order_by(desc(Application.updated_at)).all()
    result = []
    for app in apps:
        job = db.query(Job).filter(Job.id == app.job_id).first()
        d = _app_dict(app)
        if job:
            d["job"] = _job_dict(job, None)
        result.append(d)
    return result


@router.put("/applications/{app_id}")
def update_application(app_id: int, body: ApplicationUpdate, db: Session = Depends(get_db)):
    app = db.query(Application).filter(Application.id == app_id).first()
    if not app:
        raise HTTPException(404, "Not found")
    prev_stage = app.stage
    if body.stage is not None:
        app.stage = body.stage
        # Auto thank-you when reaching interview
        if body.stage == "interview" and prev_stage != "interview":
            from threading import Thread
            from thankyou import send_thankyou
            Thread(target=send_thankyou, args=(app.id, False), daemon=True).start()
            db.add(ApplicationLog(
                job_id=app.job_id, action="interview_reached",
                detail="Auto thank-you email triggered",
            ))
        # Telegram alert when interview/offer reached
        try:
            from telegram_notifier import notify_interview_detected
            if body.stage in ("interview", "offer"):
                j = db.query(Job).filter(Job.id == app.job_id).first()
                if j:
                    notify_interview_detected(j, body.stage)
        except Exception:
            pass
    if body.notes is not None:
        app.notes = body.notes
    if body.next_action is not None:
        app.next_action = body.next_action
    if body.next_action_date is not None:
        try:
            app.next_action_date = datetime.fromisoformat(body.next_action_date)
        except Exception:
            pass
    if body.response_received is not None:
        app.response_received = body.response_received
        if body.response_received:
            app.response_date = datetime.utcnow()
    app.updated_at = datetime.utcnow()
    db.commit()
    return {"ok": True}


@router.post("/applications")
def create_application(job_id: int, db: Session = Depends(get_db)):
    """Manually create application record for a job."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(404, "Job not found")
    existing = db.query(Application).filter_by(job_id=job_id).first()
    if existing:
        return {"ok": True, "id": existing.id, "existing": True}
    app = Application(job_id=job_id, stage="applied")
    db.add(app)
    job.status = "applied"
    job.applied_date = datetime.utcnow()
    db.commit()
    return {"ok": True, "id": app.id}


# ── Multi-Resume CRUD ─────────────────────────────────────────────────────────
@router.get("/resumes")
def list_resumes(db: Session = Depends(get_db)):
    resumes = db.query(ResumeProfile).order_by(desc(ResumeProfile.is_default), ResumeProfile.name).all()
    return [_resume_dict(r) for r in resumes]


@router.post("/resumes")
def create_resume(body: ResumeCreate, db: Session = Depends(get_db)):
    if body.is_default:
        db.query(ResumeProfile).update({"is_default": False})
    r = ResumeProfile(
        name=body.name,
        description=body.description,
        content=body.content,
        target_roles=json.dumps(body.target_roles or []),
        is_default=body.is_default,
        updated_at=datetime.utcnow(),
    )
    db.add(r)
    db.commit()
    db.refresh(r)
    return _resume_dict(r)


@router.get("/resumes/{resume_id}")
def get_resume(resume_id: int, db: Session = Depends(get_db)):
    r = db.query(ResumeProfile).filter(ResumeProfile.id == resume_id).first()
    if not r:
        raise HTTPException(404, "Resume not found")
    return _resume_dict(r, full=True)


@router.put("/resumes/{resume_id}")
def update_resume(resume_id: int, body: ResumeEdit, db: Session = Depends(get_db)):
    r = db.query(ResumeProfile).filter(ResumeProfile.id == resume_id).first()
    if not r:
        raise HTTPException(404, "Resume not found")
    if body.is_default:
        db.query(ResumeProfile).filter(ResumeProfile.id != resume_id).update({"is_default": False})
    if body.name is not None:
        r.name = body.name
    if body.description is not None:
        r.description = body.description
    if body.content is not None:
        r.content = body.content
    if body.target_roles is not None:
        r.target_roles = json.dumps(body.target_roles)
    if body.is_default is not None:
        r.is_default = body.is_default
    r.updated_at = datetime.utcnow()
    db.commit()
    return _resume_dict(r)


@router.delete("/resumes/{resume_id}")
def delete_resume(resume_id: int, db: Session = Depends(get_db)):
    r = db.query(ResumeProfile).filter(ResumeProfile.id == resume_id).first()
    if not r:
        raise HTTPException(404, "Resume not found")
    if r.pdf_path and os.path.exists(r.pdf_path):
        os.remove(r.pdf_path)
    db.delete(r)
    db.commit()
    return {"ok": True}


@router.post("/resumes/{resume_id}/upload-pdf")
async def upload_resume_pdf(resume_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    r = db.query(ResumeProfile).filter(ResumeProfile.id == resume_id).first()
    if not r:
        raise HTTPException(404, "Resume not found")
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files accepted")
    safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', r.name)
    filename = f"resume_{resume_id}_{safe_name}.pdf"
    path = os.path.join(_RESUMES_DIR, filename)
    with open(path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    r.pdf_path = path
    r.updated_at = datetime.utcnow()
    # Auto-extract text from PDF if resume has no content yet
    extracted_text = ""
    if not r.content or len(r.content.strip()) < 50:
        try:
            from pdf_extractor import extract_and_structure
            extracted_text = extract_and_structure(path)
            if extracted_text:
                r.content = extracted_text
                logger.info(f"Auto-extracted {len(extracted_text)} chars from PDF for resume {resume_id}")
        except Exception as e:
            logger.warning(f"PDF extraction failed: {e}")
    db.commit()
    return {
        "ok": True,
        "filename": filename,
        "extracted_text_length": len(extracted_text),
        "auto_populated": bool(extracted_text),
    }


@router.post("/resumes/upload-new")
async def upload_new_resume(
    file: UploadFile = File(...),
    name: str = "Uploaded Resume",
    db: Session = Depends(get_db),
):
    """Upload a PDF and create a new resume profile, auto-extracting text via Gemini."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files accepted")
    # Save PDF
    safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', name)
    filename = f"resume_new_{safe_name}.pdf"
    path = os.path.join(_RESUMES_DIR, filename)
    with open(path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    # Extract text
    content = ""
    try:
        from pdf_extractor import extract_and_structure
        content = extract_and_structure(path)
    except Exception as e:
        logger.warning(f"PDF extraction failed: {e}")
    # Create resume profile
    r = ResumeProfile(
        name=name,
        content=content,
        pdf_path=path,
        updated_at=datetime.utcnow(),
    )
    db.add(r)
    db.commit()
    db.refresh(r)
    # Rename file with real id
    new_path = os.path.join(_RESUMES_DIR, f"resume_{r.id}_{safe_name}.pdf")
    os.rename(path, new_path)
    r.pdf_path = new_path
    db.commit()
    return {
        "ok": True,
        "resume_id": r.id,
        "extracted_chars": len(content),
        "auto_populated": bool(content),
    }


@router.get("/resumes/{resume_id}/download-pdf")
def download_resume_pdf(resume_id: int, db: Session = Depends(get_db)):
    from fastapi.responses import FileResponse
    r = db.query(ResumeProfile).filter(ResumeProfile.id == resume_id).first()
    if not r or not r.pdf_path or not os.path.exists(r.pdf_path):
        raise HTTPException(404, "PDF not found")
    return FileResponse(r.pdf_path, media_type="application/pdf", filename=f"{r.name}.pdf")


@router.post("/resumes/{resume_id}/improve")
def improve_resume(resume_id: int, db: Session = Depends(get_db)):
    r = db.query(ResumeProfile).filter(ResumeProfile.id == resume_id).first()
    if not r or not r.content:
        raise HTTPException(400, "No resume content")
    from gemini import suggest_resume_improvements
    suggestions = suggest_resume_improvements(r.content)
    return {"ok": True, "suggestions": suggestions}


@router.post("/resumes/select-for-job/{job_id}")
def select_resume_for_job(job_id: int, db: Session = Depends(get_db)):
    """Gemini picks the best resume for this specific job."""
    j = db.query(Job).filter(Job.id == job_id).first()
    if not j:
        raise HTTPException(404, "Job not found")
    resumes = db.query(ResumeProfile).all()
    if not resumes:
        return {"ok": False, "message": "No resumes saved"}
    from gemini import select_best_resume
    resume_dicts = [{"id": r.id, "name": r.name, "content": r.content or "",
                     "target_roles": r.target_roles or "[]", "description": r.description or ""}
                    for r in resumes]
    chosen = select_best_resume(j.title, j.description or "", resume_dicts)
    if not chosen:
        chosen = resume_dicts[0]
    return {"ok": True, "selected_resume_id": chosen["id"], "selected_resume_name": chosen["name"]}


# ── Legacy single-resume endpoint (backwards compat) ─────────────────────────
@router.get("/resume")
def get_resume_legacy(db: Session = Depends(get_db)):
    r = db.query(ResumeProfile).filter_by(is_default=True).first() or \
        db.query(ResumeProfile).first()
    if not r:
        return {"content": "", "updated_at": None}
    return {"content": r.content, "updated_at": r.updated_at.isoformat() if r.updated_at else None}


@router.put("/resume")
def save_resume_legacy(body: ResumeUpdate, db: Session = Depends(get_db)):
    r = db.query(ResumeProfile).filter_by(is_default=True).first() or \
        db.query(ResumeProfile).first()
    if not r:
        r = ResumeProfile(name="Default", content=body.content, is_default=True)
        db.add(r)
    else:
        r.content = body.content
        r.updated_at = datetime.utcnow()
    db.commit()
    return {"ok": True}


@router.post("/resume/improve")
def improve_resume_legacy(db: Session = Depends(get_db)):
    r = db.query(ResumeProfile).filter_by(is_default=True).first() or \
        db.query(ResumeProfile).first()
    if not r or not r.content:
        raise HTTPException(400, "No resume saved")
    from gemini import suggest_resume_improvements
    suggestions = suggest_resume_improvements(r.content)
    return {"ok": True, "suggestions": suggestions}


# ── Stats & Analytics ─────────────────────────────────────────────────────────
# ── Offer Comparison ──────────────────────────────────────────────────────────
class OfferSaveIn(BaseModel):
    application_id: int
    base_salary: str
    bonus: str = ""
    equity: str = ""
    benefits: str = ""
    growth_score: int = 50
    culture_score: int = 50
    benefits_score: int = 50
    notes: str = ""


@router.post("/offers/save")
def save_offer(body: OfferSaveIn, db: Session = Depends(get_db)):
    from offer_comparator import save_offer as _save
    return _save(db, body.application_id, body.dict())


@router.get("/offers/list")
def list_offers_endpoint(db: Session = Depends(get_db)):
    from offer_comparator import list_offers
    return list_offers(db)


class OfferCompareIn(BaseModel):
    application_ids: list


@router.post("/offers/compare")
def compare_offers_endpoint(body: OfferCompareIn, db: Session = Depends(get_db)):
    from offer_comparator import compare_offers
    return compare_offers(db, body.application_ids)


# ── Negotiation Simulator ─────────────────────────────────────────────────────
class NegStartIn(BaseModel):
    job_title: str
    company: str
    initial_offer_inr: int
    target_inr: int


class NegContinueIn(BaseModel):
    job_title: str
    company: str
    history: list
    response: str
    current_offer: int
    target: int
    round_num: int


@router.post("/negotiation/start")
def neg_start(body: NegStartIn):
    from negotiation_sim import start_negotiation
    return start_negotiation(body.job_title, body.company, body.initial_offer_inr, body.target_inr)


@router.post("/negotiation/continue")
def neg_continue(body: NegContinueIn):
    from negotiation_sim import continue_negotiation
    return continue_negotiation(
        body.job_title, body.company, body.history, body.response,
        body.current_offer, body.target, body.round_num,
    )


# ── Backup / Restore ──────────────────────────────────────────────────────────
@router.post("/backup/create")
def backup_create():
    from backup_restore import create_backup
    return create_backup()


@router.get("/backup/list")
def backup_list():
    from backup_restore import list_backups
    return list_backups()


@router.post("/backup/restore")
def backup_restore_endpoint(filename: str):
    from backup_restore import restore_backup
    return restore_backup(filename)


# ── Slack Test ────────────────────────────────────────────────────────────────
@router.post("/slack/test")
def test_slack():
    from slack_notifier import send_slack, slack_available
    if not slack_available():
        return {
            "ok": False,
            "message": "Slack webhook not configured",
            "setup": "Add SLACK_WEBHOOK_URL=https://hooks.slack.com/... to .env",
        }
    ok = send_slack("✅ GetAJob Slack notifications are working!")
    return {"ok": ok}


# ── Achievements / Gamification ───────────────────────────────────────────────
@router.get("/achievements")
def get_achievements(db: Session = Depends(get_db)):
    from achievements import get_unlocked
    return get_unlocked(db)


# ── AI Coach Chat ─────────────────────────────────────────────────────────────
class CoachChatIn(BaseModel):
    history: list = []
    message: str


@router.post("/coach/chat")
def coach_chat(body: CoachChatIn):
    from ai_chat import chat
    return chat(body.history, body.message)


# ── WhatsApp Test ─────────────────────────────────────────────────────────────
@router.post("/whatsapp/test")
def test_whatsapp():
    from whatsapp_notifier import send_whatsapp, whatsapp_available
    if not whatsapp_available():
        return {
            "ok": False,
            "message": "WhatsApp not configured",
            "setup": [
                "1. Sign up at https://www.twilio.com (free)",
                "2. Join WhatsApp Sandbox at /console/sms/whatsapp/sandbox",
                "3. Add to .env:",
                "   TWILIO_ACCOUNT_SID=...",
                "   TWILIO_AUTH_TOKEN=...",
                "   TWILIO_WHATSAPP_TO=whatsapp:+919XXXXXXXXX",
                "4. Restart server",
            ],
        }
    ok = send_whatsapp("✅ GetAJob WhatsApp notifications are working!")
    return {"ok": ok}


# ── System Health ─────────────────────────────────────────────────────────────
@router.get("/health")
def system_health():
    from health import check_health
    return check_health()


# ── Onboarding ────────────────────────────────────────────────────────────────
@router.get("/onboarding")
def onboarding_status(db: Session = Depends(get_db)):
    from onboarding import get_onboarding_status
    return get_onboarding_status(db)


# ── Daily Playbook ────────────────────────────────────────────────────────────
@router.get("/playbook/today")
def playbook_today(db: Session = Depends(get_db)):
    """Returns today's 2-hour structured playbook with timed tasks."""
    from daily_playbook import get_daily_playbook
    return get_daily_playbook(db)


# ── Reply Detector ────────────────────────────────────────────────────────────
@router.post("/replies/check")
def check_replies(dry_run: bool = True, background_tasks: BackgroundTasks = None):
    from reply_detector import check_for_replies
    if background_tasks:
        background_tasks.add_task(check_for_replies, dry_run)
        return {"ok": True, "queued": True}
    return check_for_replies(dry_run=dry_run)


# ── Recruiter Call Simulator ──────────────────────────────────────────────────
class RecruiterCallStart(BaseModel):
    job_id: int

class RecruiterCallContinue(BaseModel):
    job_id: int
    history: list
    answer: str
    question_index: int


@router.post("/recruiter-call/start")
def recruiter_call_start(body: RecruiterCallStart, db: Session = Depends(get_db)):
    j = db.query(Job).filter(Job.id == body.job_id).first()
    if not j:
        raise HTTPException(404, "Job not found")
    from recruiter_call_sim import start_recruiter_call
    return start_recruiter_call(j.title, j.company)


@router.post("/recruiter-call/continue")
def recruiter_call_continue(body: RecruiterCallContinue, db: Session = Depends(get_db)):
    j = db.query(Job).filter(Job.id == body.job_id).first()
    if not j:
        raise HTTPException(404, "Job not found")
    from recruiter_call_sim import continue_recruiter_call
    return continue_recruiter_call(
        j.title, j.company, body.history, body.answer, body.question_index,
    )


# ── Success Predictor ─────────────────────────────────────────────────────────
@router.get("/success-predictor")
def success_predictor(target_days: int = 90, db: Session = Depends(get_db)):
    """Returns probability of getting an offer within target_days + actions to maximize it."""
    from success_predictor import predict_success
    return predict_success(db, target_days=target_days)


# ── Form Auto-fill Kit ────────────────────────────────────────────────────────
@router.get("/autofill/pack")
def autofill_pack(job_id: int = 0, db: Session = Depends(get_db)):
    """Returns autofill JSON for ATS application forms."""
    from form_filler_kit import build_autofill_pack
    cl = ""
    title = ""
    company = ""
    if job_id:
        j = db.query(Job).filter(Job.id == job_id).first()
        if j:
            title = j.title
            company = j.company
            a = db.query(AIAnalysis).filter_by(job_id=job_id).first()
            if a:
                cl = a.cover_letter or ""
    return build_autofill_pack(title, company, cl)


@router.get("/autofill/bookmarklet")
def autofill_bookmarklet(job_id: int = 0, db: Session = Depends(get_db)):
    """Returns a javascript: URL bookmarklet for one-click autofill."""
    from form_filler_kit import build_autofill_pack, generate_browser_bookmark_js
    cl = ""
    if job_id:
        a = db.query(AIAnalysis).filter_by(job_id=job_id).first()
        if a:
            cl = a.cover_letter or ""
    pack = build_autofill_pack("", "", cl)
    js = generate_browser_bookmark_js(pack)
    return {"bookmarklet": js, "instructions": "Drag this JS into your bookmarks bar. Click it on any ATS application form to autofill."}


# ── Visa / Work Authorization Filter ──────────────────────────────────────────
@router.get("/jobs/{job_id}/visa-check")
def visa_check(job_id: int, db: Session = Depends(get_db)):
    from visa_filter import classify_visa
    j = db.query(Job).filter(Job.id == job_id).first()
    if not j:
        raise HTTPException(404, "Job not found")
    return classify_visa(j.description or "", j.location or "")


@router.get("/accessible-jobs")
def accessible_jobs(
    min_score: int = 60,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """Jobs filtered by visa accessibility (no visa-blocking ones)."""
    from visa_filter import classify_visa
    jobs = (
        db.query(Job)
        .filter(Job.match_score >= min_score, Job.status == "new")
        .order_by(desc(Job.match_score))
        .limit(200)
        .all()
    )
    open_jobs = []
    for j in jobs:
        v = classify_visa(j.description or "", j.location or "")
        if v["accessibility"] != "blocked":
            j_dict = _job_dict(j, None)
            j_dict["visa"] = v
            open_jobs.append(j_dict)
    total = len(open_jobs)
    return {"total": total, "jobs": open_jobs[skip:skip + limit]}


# ── Cover Letter A/B Testing ──────────────────────────────────────────────────
@router.get("/cover-letter-ab/stats")
def cover_letter_ab_stats(db: Session = Depends(get_db)):
    from cover_letter_ab import get_variant_stats, COVER_LETTER_VARIANTS
    stats = get_variant_stats(db)
    return {
        "variants": stats,
        "all_variants": [{"key": k, "name": v["name"], "instructions": v["instructions"]}
                         for k, v in COVER_LETTER_VARIANTS.items()],
    }


# ── Response Time Analytics ───────────────────────────────────────────────────
@router.get("/analytics/response-times")
def response_time_analytics(db: Session = Depends(get_db)):
    from response_analytics import compute_response_analytics
    return compute_response_analytics(db)


@router.get("/stats")
def get_stats(db: Session = Depends(get_db)):
    total = db.query(Job).count()
    new = db.query(Job).filter(Job.status == "new").count()
    saved = db.query(Job).filter(Job.status == "saved").count()
    applied = db.query(Job).filter(Job.status == "applied").count()
    rejected = db.query(Job).filter(Job.status == "rejected").count()
    high_match = db.query(Job).filter(Job.match_score >= 80, Job.status == "new").count()
    ai_analyzed = db.query(AIAnalysis).count()
    auto_applied = db.query(Job).filter(Job.auto_applied == True).count()
    pipeline = {
        "applied": db.query(Application).filter(Application.stage == "applied").count(),
        "phone_screen": db.query(Application).filter(Application.stage == "phone_screen").count(),
        "interview": db.query(Application).filter(Application.stage == "interview").count(),
        "offer": db.query(Application).filter(Application.stage == "offer").count(),
    }
    return {
        "total": total, "new": new, "saved": saved, "applied": applied,
        "rejected": rejected, "high_match": high_match,
        "ai_analyzed": ai_analyzed, "auto_applied": auto_applied,
        "pipeline": pipeline,
    }


@router.get("/analytics")
def get_analytics(db: Session = Depends(get_db)):
    jobs = db.query(Job).all()
    by_source = {}
    by_score_bucket = {"0-40": 0, "41-60": 0, "61-80": 0, "81-100": 0}
    by_status = {}
    for j in jobs:
        by_source[j.source] = by_source.get(j.source, 0) + 1
        by_status[j.status] = by_status.get(j.status, 0) + 1
        if j.match_score <= 40: by_score_bucket["0-40"] += 1
        elif j.match_score <= 60: by_score_bucket["41-60"] += 1
        elif j.match_score <= 80: by_score_bucket["61-80"] += 1
        else: by_score_bucket["81-100"] += 1

    apps = db.query(Application).all()
    response_rate = (
        round(sum(1 for a in apps if a.response_received) / len(apps) * 100, 1)
        if apps else 0
    )
    return {
        "by_source": by_source,
        "by_score_bucket": by_score_bucket,
        "by_status": by_status,
        "total_jobs": len(jobs),
        "total_applications": len(apps),
        "response_rate": response_rate,
    }


# ── Actions ───────────────────────────────────────────────────────────────────
@router.post("/jobs/{job_id}/interview-prep")
def get_interview_prep(job_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    j = db.query(Job).filter(Job.id == job_id).first()
    if not j:
        raise HTTPException(404, "Job not found")
    analysis = db.query(AIAnalysis).filter_by(job_id=job_id).first()
    if analysis and getattr(analysis, 'interview_prep', None):
        import json as _j
        try:
            return {"ok": True, "cached": True, "prep": _j.loads(analysis.interview_prep)}
        except Exception:
            pass
    background_tasks.add_task(_run_interview_prep, job_id)
    return {"ok": True, "cached": False, "message": "Interview prep generating — refresh in 60s"}


def _run_interview_prep(job_id: int):
    from interview_prep import get_or_generate_prep
    get_or_generate_prep(job_id)


# ── Follow-ups ────────────────────────────────────────────────────────────────
@router.post("/followups/run")
def trigger_followups(dry_run: bool = True, background_tasks: BackgroundTasks = None):
    from followup import run_followups
    if background_tasks:
        background_tasks.add_task(run_followups, dry_run)
        return {"ok": True, "message": f"Follow-up cycle queued (dry_run={dry_run})"}
    return {"ok": True, "result": run_followups(dry_run=dry_run)}


@router.get("/followups/due")
def list_due_followups(db: Session = Depends(get_db)):
    """List applications where a follow-up email is overdue."""
    from datetime import timedelta
    now = datetime.utcnow()
    apps = (
        db.query(Application)
        .filter(Application.email_sent == True, Application.response_received == False)
        .all()
    )
    due = []
    for app in apps:
        if not app.email_sent_at or not app.hr_email:
            continue
        count = app.follow_up_count or 0
        if count >= 2:
            continue
        thresholds = [7, 14]
        due_at = app.email_sent_at + timedelta(days=thresholds[count])
        if now >= due_at:
            job = db.query(Job).filter(Job.id == app.job_id).first()
            due.append({
                "application_id": app.id,
                "job_id": app.job_id,
                "job_title": job.title if job else "",
                "company": job.company if job else "",
                "hr_email": app.hr_email,
                "applied_at": app.email_sent_at.isoformat() if app.email_sent_at else None,
                "follow_up_num": count + 1,
                "days_overdue": int((now - due_at).total_seconds() / 86400),
            })
    return sorted(due, key=lambda x: x["days_overdue"], reverse=True)


# ── Telegram setup ────────────────────────────────────────────────────────────
@router.get("/telegram/status")
def telegram_status():
    from telegram_notifier import telegram_available, _BOT_TOKEN
    return {
        "configured": telegram_available(),
        "has_token": bool(_BOT_TOKEN),
        "setup_steps": [
            "1. Open Telegram → search @BotFather → /newbot",
            "2. Copy the token → add TELEGRAM_BOT_TOKEN=<token> to .env",
            "3. Message your bot once",
            "4. Call GET /api/telegram/get-chat-id?token=<token>",
            "5. Add TELEGRAM_CHAT_ID=<id> to .env",
            "6. Restart server",
        ],
    }


@router.get("/telegram/get-chat-id")
def get_telegram_chat_id(token: str):
    from telegram_notifier import get_chat_id
    chat_id = get_chat_id(token)
    if chat_id:
        return {"chat_id": chat_id, "next": f"Add TELEGRAM_CHAT_ID={chat_id} to .env"}
    return {"error": "No messages found. Message your bot first, then retry."}


@router.post("/telegram/test")
def test_telegram():
    from telegram_notifier import send
    ok = send("✅ GetAJob Telegram notifications are working!")
    return {"ok": ok, "message": "sent" if ok else "failed — check TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env"}


# ── Funnel Analytics ──────────────────────────────────────────────────────────
@router.get("/analytics/funnel")
def get_funnel(db: Session = Depends(get_db)):
    total = db.query(Job).count()
    scored_60 = db.query(Job).filter(Job.match_score >= 60).count()
    scored_80 = db.query(Job).filter(Job.match_score >= 80).count()
    ai_analyzed = db.query(AIAnalysis).count()
    ai_recommended = db.query(AIAnalysis).filter(AIAnalysis.apply_recommended == True).count()
    applied = db.query(Job).filter(Job.status == "applied").count()
    phone_screen = db.query(Application).filter(Application.stage == "phone_screen").count()
    interview = db.query(Application).filter(Application.stage == "interview").count()
    offer = db.query(Application).filter(Application.stage == "offer").count()
    return {
        "funnel": [
            {"stage": "Scraped", "count": total, "pct": 100},
            {"stage": "Score 60+", "count": scored_60, "pct": round(scored_60/max(total,1)*100)},
            {"stage": "Score 80+", "count": scored_80, "pct": round(scored_80/max(total,1)*100)},
            {"stage": "AI Analyzed", "count": ai_analyzed, "pct": round(ai_analyzed/max(total,1)*100)},
            {"stage": "AI Recommended", "count": ai_recommended, "pct": round(ai_recommended/max(ai_analyzed,1)*100)},
            {"stage": "Applied", "count": applied, "pct": round(applied/max(total,1)*100)},
            {"stage": "Phone Screen", "count": phone_screen, "pct": round(phone_screen/max(applied,1)*100)},
            {"stage": "Interview", "count": interview, "pct": round(interview/max(applied,1)*100)},
            {"stage": "Offer", "count": offer, "pct": round(offer/max(applied,1)*100)},
        ]
    }


@router.post("/analyze/all")
def batch_analyze_all(background_tasks: BackgroundTasks):
    """Trigger Gemini analysis on ALL unanalyzed jobs in parallel (4 workers)."""
    from gemini import analyze_all_jobs_batch, get_batch_progress
    if get_batch_progress()["running"]:
        return {"ok": False, "message": "Batch analysis already running"}
    background_tasks.add_task(analyze_all_jobs_batch, 4)
    return {"ok": True, "message": "Batch analysis started — poll /api/analyze/progress"}


@router.get("/analyze/progress")
def batch_analyze_progress():
    from gemini import get_batch_progress
    return get_batch_progress()


# ── Export ────────────────────────────────────────────────────────────────────
@router.get("/export/applications.csv")
def export_applications(db: Session = Depends(get_db)):
    from fastapi.responses import Response
    from exporter import export_applications_csv
    csv_data = export_applications_csv(db)
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=applications.csv"},
    )


@router.get("/export/jobs.csv")
def export_jobs(min_score: int = 60, db: Session = Depends(get_db)):
    from fastapi.responses import Response
    from exporter import export_jobs_csv
    csv_data = export_jobs_csv(db, min_score)
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=jobs.csv"},
    )


# ── ATS Optimizer ─────────────────────────────────────────────────────────────
@router.post("/jobs/{job_id}/ats-check")
def ats_check(job_id: int, db: Session = Depends(get_db)):
    j = db.query(Job).filter(Job.id == job_id).first()
    if not j:
        raise HTTPException(404, "Job not found")
    resume = db.query(ResumeProfile).filter_by(is_default=True).first() or \
             db.query(ResumeProfile).first()
    if not resume:
        return {"error": "No resume saved. Add a resume in the Resumes tab first."}
    from ats_optimizer import gemini_ats_analysis
    result = gemini_ats_analysis(j.title, j.description or "", resume.content or "")
    return {"ok": True, "job_id": job_id, "ats": result}


# ── Daily Recommendations ─────────────────────────────────────────────────────
@router.get("/recommendations/daily")
def daily_recommendations(db: Session = Depends(get_db)):
    """Gemini picks top 3 jobs to apply to today."""
    from recommender import get_daily_top3
    return {"top3": get_daily_top3(db)}


@router.post("/cleanup")
def trigger_cleanup(days: int = 60, background_tasks: BackgroundTasks = None, db: Session = Depends(get_db)):
    """Remove stale low-score jobs."""
    from recommender import cleanup_old_jobs
    count = cleanup_old_jobs(db, days=days)
    return {"ok": True, "removed": count}


# ── Thank-you trigger ─────────────────────────────────────────────────────────
@router.post("/applications/{app_id}/thank-you")
def send_thank_you(app_id: int, dry_run: bool = True, background_tasks: BackgroundTasks = None):
    from thankyou import send_thankyou
    if background_tasks:
        background_tasks.add_task(send_thankyou, app_id, dry_run)
        return {"ok": True, "queued": True, "dry_run": dry_run}
    ok = send_thankyou(app_id, dry_run)
    return {"ok": ok, "dry_run": dry_run}


# ── Calendar Export ───────────────────────────────────────────────────────────
@router.get("/calendar.ics")
def calendar_feed(db: Session = Depends(get_db)):
    """Subscribable ICS calendar feed of all interviews + follow-up reminders."""
    from fastapi.responses import Response
    from calendar_export import build_calendar_ics
    ics = build_calendar_ics(db)
    return Response(
        content=ics,
        media_type="text/calendar",
        headers={"Content-Disposition": "attachment; filename=getajob.ics"},
    )


@router.get("/applications/{app_id}/calendar")
def app_calendar(app_id: int, interview_date: str, db: Session = Depends(get_db)):
    from fastapi.responses import Response
    from calendar_export import single_interview_ics
    ics = single_interview_ics(app_id, interview_date, db)
    return Response(
        content=ics,
        media_type="text/calendar",
        headers={"Content-Disposition": f"attachment; filename=interview_{app_id}.ics"},
    )


# ── Outreach Templates ────────────────────────────────────────────────────────
@router.get("/outreach/templates")
def get_templates():
    from outreach_templates import list_templates
    return list_templates()


class OutreachIn(BaseModel):
    template_key: str
    target_company: str
    target_role: str
    target_person_name: str = ""
    target_person_role: str = ""
    personalize_with_gemini: bool = True


@router.post("/outreach/personalize")
def personalize_outreach(body: OutreachIn):
    from outreach_templates import gemini_personalize, personalize_template
    if body.personalize_with_gemini:
        msg = gemini_personalize(
            body.template_key, body.target_company, body.target_role,
            body.target_person_name, body.target_person_role,
        )
    else:
        msg = personalize_template(body.template_key, {
            "company": body.target_company,
            "role": body.target_role,
            "first_name": body.target_person_name or "there",
            "hr_name": body.target_person_name or "Hiring Manager",
        })
    return {"ok": True, "message": msg, "length": len(msg)}


class OutreachLogIn(BaseModel):
    template_key: str
    target_company: str
    target_person: str = ""
    channel: str = "linkedin"
    message_text: str


@router.post("/outreach/log")
def log_outreach(body: OutreachLogIn, db: Session = Depends(get_db)):
    from database import OutreachLog
    log = OutreachLog(
        template_key=body.template_key,
        target_company=body.target_company,
        target_person=body.target_person,
        channel=body.channel,
        message_text=body.message_text,
    )
    db.add(log)
    db.commit()
    return {"ok": True, "id": log.id}


@router.get("/outreach/stats")
def outreach_stats(db: Session = Depends(get_db)):
    """Response rate by template — A/B testing data."""
    from database import OutreachLog
    logs = db.query(OutreachLog).all()
    by_template = {}
    for l in logs:
        k = l.template_key
        if k not in by_template:
            by_template[k] = {"sent": 0, "responses": 0}
        by_template[k]["sent"] += 1
        if l.got_response:
            by_template[k]["responses"] += 1
    for k, v in by_template.items():
        v["response_rate"] = round(v["responses"] / max(v["sent"], 1) * 100, 1)
    return {"by_template": by_template, "total_sent": len(logs)}


# ── Company Watchlist ─────────────────────────────────────────────────────────
class WatchIn(BaseModel):
    company: str
    role_filter: str = ""
    min_score: int = 50


@router.get("/watchlist")
def get_watchlist(db: Session = Depends(get_db)):
    from company_watch import list_watches
    return list_watches(db)


@router.post("/watchlist")
def add_to_watchlist(body: WatchIn, db: Session = Depends(get_db)):
    from company_watch import add_watch
    return add_watch(db, body.company, body.role_filter, body.min_score)


@router.delete("/watchlist/{watch_id}")
def remove_from_watchlist(watch_id: int, db: Session = Depends(get_db)):
    from company_watch import remove_watch
    return {"ok": remove_watch(db, watch_id)}


@router.post("/watchlist/check-alerts")
def check_watchlist_alerts(db: Session = Depends(get_db)):
    from company_watch import check_alerts
    return {"alerts_sent": check_alerts(db)}


# ── Coding Practice Tracker ───────────────────────────────────────────────────
@router.get("/coding/daily")
def coding_daily(target_role: str = "Mobile Developer", db: Session = Depends(get_db)):
    from coding_practice import get_daily_problem
    return get_daily_problem(db, target_role)


@router.post("/coding/{date_str}/complete")
def coding_complete(date_str: str, db: Session = Depends(get_db)):
    from coding_practice import mark_completed
    return mark_completed(db, date_str)


@router.get("/coding/streak")
def coding_streak(db: Session = Depends(get_db)):
    from coding_practice import get_streak
    return get_streak(db)


# ── Salary Intelligence ───────────────────────────────────────────────────────
@router.get("/salary-intel")
def salary_intel(role: str = "", location: str = "", db: Session = Depends(get_db)):
    from salary_intel import get_salary_intelligence
    return get_salary_intelligence(db, role_keyword=role, location_keyword=location)


# ── Application Heatmap ───────────────────────────────────────────────────────
@router.get("/heatmap")
def get_heatmap(days: int = 60, db: Session = Depends(get_db)):
    from heatmap import get_heatmap_data
    return get_heatmap_data(db, days=days)


# ── Network Outreach ──────────────────────────────────────────────────────────
@router.get("/network/outreach")
def network_outreach(db: Session = Depends(get_db)):
    from network_outreach import get_outreach_suggestions
    return get_outreach_suggestions(db)


# ── Re-apply Detection ────────────────────────────────────────────────────────
@router.get("/reapply/candidates")
def reapply_candidates(db: Session = Depends(get_db)):
    from reapply_detector import get_reapply_candidates
    return get_reapply_candidates(db)


# ── Skill Coach ───────────────────────────────────────────────────────────────
@router.get("/skill-coach/analysis")
def get_skill_analysis(db: Session = Depends(get_db)):
    from skill_coach import analyze_skill_gaps
    return analyze_skill_gaps(db)


# ── Mock Interview ────────────────────────────────────────────────────────────
class MockStartIn(BaseModel):
    job_id: int

class MockContinueIn(BaseModel):
    job_id: int
    history: list
    answer: str


@router.post("/mock-interview/start")
def mock_start(body: MockStartIn, db: Session = Depends(get_db)):
    j = db.query(Job).filter(Job.id == body.job_id).first()
    if not j:
        raise HTTPException(404, "Job not found")
    from mock_interview import start_mock_interview
    return start_mock_interview(j.title, j.company, j.description or "")


@router.post("/mock-interview/continue")
def mock_continue(body: MockContinueIn, db: Session = Depends(get_db)):
    j = db.query(Job).filter(Job.id == body.job_id).first()
    if not j:
        raise HTTPException(404, "Job not found")
    from mock_interview import continue_mock_interview
    return continue_mock_interview(j.title, j.company, body.history, body.answer)


class MockFeedbackIn(BaseModel):
    job_title: str
    history: list


@router.post("/mock-interview/feedback")
def mock_feedback(body: MockFeedbackIn):
    from mock_interview import get_final_feedback
    return {"feedback": get_final_feedback(body.job_title, body.history)}


# ── Reference Letter ──────────────────────────────────────────────────────────
class ReferenceIn(BaseModel):
    reference_name: str
    role_at_previous_company: str
    company: str
    target_role: str = ""


@router.post("/reference-letter/generate")
def gen_reference_letter(body: ReferenceIn):
    from reference_letter import generate_reference_request
    text = generate_reference_request(
        body.reference_name, body.role_at_previous_company,
        body.company, body.target_role,
    )
    return {"ok": True, "letter": text}


# ── Goals Tracker ─────────────────────────────────────────────────────────────
@router.get("/goals")
def get_goals(db: Session = Depends(get_db)):
    from config import WEEKLY_APPLY_GOAL
    from datetime import timedelta
    week_ago = datetime.utcnow() - timedelta(days=7)
    applied_this_week = db.query(Job).filter(Job.applied_date >= week_ago).count()
    total_applied = db.query(Job).filter(Job.status == "applied").count()
    high_match_remaining = db.query(Job).filter(
        Job.match_score >= 80, Job.status == "new"
    ).count()
    return {
        "weekly_goal": WEEKLY_APPLY_GOAL,
        "applied_this_week": applied_this_week,
        "goal_progress_pct": min(round(applied_this_week / max(WEEKLY_APPLY_GOAL, 1) * 100), 100),
        "goal_met": applied_this_week >= WEEKLY_APPLY_GOAL,
        "total_applied_ever": total_applied,
        "high_match_remaining": high_match_remaining,
        "suggested_action": (
            "🎯 Weekly goal met! Keep going." if applied_this_week >= WEEKLY_APPLY_GOAL
            else f"Apply to {WEEKLY_APPLY_GOAL - applied_this_week} more this week to hit goal."
        ),
    }


# ── Weekly Report ─────────────────────────────────────────────────────────────
@router.post("/weekly-report/send")
def trigger_weekly_report(background_tasks: BackgroundTasks):
    from weekly_report import send_weekly_report
    background_tasks.add_task(send_weekly_report)
    return {"ok": True, "message": "Weekly report queued"}


# ── Blacklist ─────────────────────────────────────────────────────────────────
@router.get("/config/blacklist")
def get_blacklist():
    from config import BLACKLIST_COMPANIES, BLACKLIST_KEYWORDS
    return {
        "companies": BLACKLIST_COMPANIES,
        "keywords": BLACKLIST_KEYWORDS,
        "note": "Edit BLACKLIST_COMPANIES and BLACKLIST_KEYWORDS in .env to update",
    }


@router.post("/scrape")
def trigger_scrape(background_tasks: BackgroundTasks):
    from scheduler import run_all_scrapers
    background_tasks.add_task(run_all_scrapers)
    return {"ok": True, "message": "Scrape started"}


@router.post("/digest")
def trigger_digest(background_tasks: BackgroundTasks):
    from scheduler import send_daily_digest
    background_tasks.add_task(send_daily_digest)
    return {"ok": True, "message": "Digest queued"}


@router.post("/auto-apply/run")
def trigger_auto_apply(dry_run: bool = True, background_tasks: BackgroundTasks = None):
    from auto_apply import run_auto_apply
    if background_tasks:
        background_tasks.add_task(run_auto_apply, dry_run)
        return {"ok": True, "message": f"Auto-apply started (dry_run={dry_run})"}
    result = run_auto_apply(dry_run=dry_run)
    return {"ok": True, "result": result}


@router.get("/logs")
def get_logs(skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    logs = db.query(ScrapeLog).order_by(desc(ScrapeLog.timestamp)).offset(skip).limit(limit).all()
    return [
        {
            "id": l.id, "source": l.source,
            "timestamp": l.timestamp.isoformat() if l.timestamp else None,
            "jobs_found": l.jobs_found, "jobs_new": l.jobs_new,
            "duration_seconds": l.duration_seconds, "error": l.error,
        }
        for l in logs
    ]


# ── Application Activity Logs ─────────────────────────────────────────────────
@router.get("/activity")
def get_activity(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """Full chronological log of all actions taken."""
    logs = (
        db.query(ApplicationLog)
        .order_by(desc(ApplicationLog.timestamp))
        .offset(skip).limit(limit).all()
    )
    result = []
    for l in logs:
        entry = {
            "id": l.id, "action": l.action, "detail": l.detail,
            "timestamp": l.timestamp.isoformat() if l.timestamp else None,
            "job_id": l.job_id,
        }
        if l.job_id:
            job = db.query(Job).filter(Job.id == l.job_id).first()
            if job:
                entry["job_title"] = job.title
                entry["company"] = job.company
        result.append(entry)
    return result


def _log_action(db, job_id: Optional[int], action: str, detail: str = ""):
    log = ApplicationLog(job_id=job_id, action=action, detail=detail)
    db.add(log)
    db.commit()


# ── LinkedIn Messaging ────────────────────────────────────────────────────────
@router.post("/jobs/{job_id}/linkedin-message")
def linkedin_message(job_id: int, dry_run: bool = True, db: Session = Depends(get_db)):
    j = db.query(Job).filter(Job.id == job_id).first()
    if not j:
        raise HTTPException(404, "Job not found")
    from linkedin_messenger import find_recruiter_and_message, generate_linkedin_message
    ai = db.query(AIAnalysis).filter_by(job_id=job_id).first()
    cl_snippet = (ai.cover_letter or "")[:100] if ai else ""
    message = generate_linkedin_message(j.title, j.company, cl_snippet)
    result = find_recruiter_and_message(
        company=j.company, job_title=j.title,
        job_id=job_id, message_template=message, dry_run=dry_run,
    )
    _log_action(db, job_id, "linkedin_message",
                f"dry_run={dry_run} status={result.get('status')} msg={message[:100]}")
    return {"ok": True, "result": result, "message_preview": message}


@router.get("/linkedin-logs")
def get_linkedin_logs(skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    logs = db.query(LinkedInLog).order_by(desc(LinkedInLog.created_at)).offset(skip).limit(limit).all()
    return [
        {
            "id": l.id, "job_id": l.job_id, "company": l.company,
            "recruiter_name": l.recruiter_name, "recruiter_url": l.recruiter_url,
            "message_sent": l.message_sent, "status": l.status,
            "sent_at": l.sent_at.isoformat() if l.sent_at else None,
        }
        for l in logs
    ]


# ── Qualification Filter ──────────────────────────────────────────────────────
@router.get("/qualified-jobs")
def list_qualified_jobs(
    min_score: int = 50,
    max_exp_years: int = 3,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """Returns only jobs where experience requirement <= max_exp_years."""
    from experience_filter import extract_required_experience
    jobs = (
        db.query(Job)
        .filter(Job.match_score >= min_score, Job.status == "new")
        .order_by(desc(Job.match_score))
        .all()
    )
    qualified = []
    for j in jobs:
        req = extract_required_experience(j.description or "")
        if req is None or req <= max_exp_years:
            qualified.append(j)
    total = len(qualified)
    page = qualified[skip: skip + limit]
    analyses = {a.job_id: a for a in db.query(AIAnalysis).filter(
        AIAnalysis.job_id.in_([j.id for j in page])
    ).all()}
    return {"total": total, "jobs": [_job_dict(j, analyses.get(j.id)) for j in page]}


# ── Helpers ───────────────────────────────────────────────────────────────────
def _run_analysis(job_id: int):
    from database import SessionLocal, ApplicationLog
    from gemini import analyze_job
    db = SessionLocal()
    try:
        j = db.query(Job).filter(Job.id == job_id).first()
        if not j:
            return
        result = analyze_job(j.title, j.company, j.location or "", j.description or "")
        if not result:
            return
        existing = db.query(AIAnalysis).filter_by(job_id=job_id).first()
        if existing:
            _update_analysis(existing, result)
        else:
            a = AIAnalysis(
                job_id=job_id,
                ai_score=result["ai_score"],
                match_reasons=json.dumps(result["match_reasons"]),
                red_flags=json.dumps(result["red_flags"]),
                skill_gaps=json.dumps(result["skill_gaps"]),
                suggested_salary=result["suggested_salary"],
                apply_recommended=result["apply_recommended"],
                one_line_summary=result["one_line_summary"],
            )
            db.add(a)
        # Log the analysis action
        exp_req = result.get("required_experience_years")
        exp_ok = result.get("experience_match", True)
        log = ApplicationLog(
            job_id=job_id,
            action="ai_analyzed",
            detail=f"ai_score={result['ai_score']} exp_required={exp_req}yr exp_ok={exp_ok} apply={result['apply_recommended']}",
        )
        db.add(log)
        db.commit()
    except Exception as e:
        logger.error(f"Analysis task error for job {job_id}: {e}")
    finally:
        db.close()


def _update_analysis(a: AIAnalysis, result: dict):
    a.ai_score = result["ai_score"]
    a.match_reasons = json.dumps(result["match_reasons"])
    a.red_flags = json.dumps(result["red_flags"])
    a.skill_gaps = json.dumps(result["skill_gaps"])
    a.suggested_salary = result["suggested_salary"]
    a.apply_recommended = result["apply_recommended"]
    a.one_line_summary = result["one_line_summary"]
    a.analyzed_at = datetime.utcnow()


def _job_dict(j: Job, analysis: AIAnalysis = None, full: bool = False) -> dict:
    d = {
        "id": j.id, "source": j.source, "title": j.title, "company": j.company,
        "location": j.location, "salary_text": j.salary_text, "salary_min": j.salary_min,
        "url": j.url, "match_score": j.match_score, "status": j.status,
        "found_date": j.found_date.isoformat() if j.found_date else None,
        "posted_date": j.posted_date.isoformat() if j.posted_date else None,
        "applied_date": j.applied_date.isoformat() if j.applied_date else None,
        "notes": j.notes, "notified": j.notified, "auto_applied": j.auto_applied,
        "has_ai": analysis is not None,
        "ai": _analysis_dict(analysis) if analysis else None,
    }
    if full:
        d["description"] = j.description
    return d


def _analysis_dict(a: AIAnalysis) -> dict:
    if not a:
        return None
    def safe_json(val):
        if not val:
            return []
        try:
            return json.loads(val) if isinstance(val, str) else val
        except Exception:
            return []
    return {
        "ai_score": a.ai_score,
        "match_reasons": safe_json(a.match_reasons),
        "red_flags": safe_json(a.red_flags),
        "skill_gaps": safe_json(a.skill_gaps),
        "suggested_salary": a.suggested_salary,
        "apply_recommended": a.apply_recommended,
        "one_line_summary": a.one_line_summary,
        "cover_letter": a.cover_letter,
        "tailored_resume": a.tailored_resume,
        "hr_email": a.hr_email,
        "analyzed_at": a.analyzed_at.isoformat() if a.analyzed_at else None,
        "required_experience_years": getattr(a, "required_experience_years", None),
        "experience_qualified": getattr(a, "experience_qualified", None),
    }


def _resume_dict(r: ResumeProfile, full: bool = False) -> dict:
    def safe_roles(val):
        if not val:
            return []
        try:
            parsed = json.loads(val) if isinstance(val, str) else val
            return parsed if isinstance(parsed, list) else []
        except Exception:
            return []
    d = {
        "id": r.id,
        "name": r.name,
        "description": r.description,
        "target_roles": safe_roles(r.target_roles),
        "has_pdf": bool(r.pdf_path and os.path.exists(r.pdf_path)),
        "is_default": r.is_default,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
        "content_preview": (r.content or "")[:200],
    }
    if full:
        d["content"] = r.content
    return d


def _app_dict(a: Application) -> dict:
    return {
        "id": a.id, "job_id": a.job_id, "stage": a.stage,
        "hr_email": a.hr_email, "email_sent": a.email_sent,
        "email_sent_at": a.email_sent_at.isoformat() if a.email_sent_at else None,
        "response_received": a.response_received,
        "response_date": a.response_date.isoformat() if a.response_date else None,
        "next_action": a.next_action,
        "next_action_date": a.next_action_date.isoformat() if a.next_action_date else None,
        "notes": a.notes,
        "created_at": a.created_at.isoformat() if a.created_at else None,
        "updated_at": a.updated_at.isoformat() if a.updated_at else None,
    }
