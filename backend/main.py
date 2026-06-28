import logging
import os
import threading

import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse

from api import router
from database import Job, SessionLocal, init_db
from scheduler import run_all_scrapers, setup_scheduler

_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
os.makedirs(_DATA_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(_DATA_DIR, "getajob.log")),
    ],
)
logger = logging.getLogger(__name__)

_FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")
_FRONTEND = os.path.join(_FRONTEND_DIR, "index.html")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    logger.info("DB initialized")
    scheduler = setup_scheduler()
    scheduler.start()
    logger.info("Scheduler started — scrape every 12h, digest daily")
    db = SessionLocal()
    count = db.query(Job).count()
    db.close()
    if count == 0:
        logger.info("Empty DB — running initial scrape in background...")
        t = threading.Thread(target=run_all_scrapers, daemon=True)
        t.start()
    yield
    logger.info("GetAJob shutting down")


app = FastAPI(title="GetAJob", version="1.0", lifespan=lifespan)
app.include_router(router)


@app.get("/")
def root():
    if os.path.exists(_FRONTEND):
        return FileResponse(_FRONTEND)
    return JSONResponse({"status": "running", "dashboard": "/api/jobs"})


@app.get("/manifest.webmanifest")
def manifest():
    p = os.path.join(_FRONTEND_DIR, "manifest.webmanifest")
    if os.path.exists(p):
        return FileResponse(p, media_type="application/manifest+json")
    return JSONResponse({"error": "no manifest"}, status_code=404)


@app.get("/sw.js")
def service_worker():
    p = os.path.join(_FRONTEND_DIR, "sw.js")
    if os.path.exists(p):
        return FileResponse(p, media_type="application/javascript")
    return JSONResponse({"error": "no sw"}, status_code=404)


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False, log_level="info")
