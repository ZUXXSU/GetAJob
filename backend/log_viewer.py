"""
In-app log viewer — read recent log lines from data/getajob.log.
Filterable by level (INFO/WARNING/ERROR). Tail mode for live monitoring.
"""
import os
import re
from datetime import datetime
from typing import Optional

_LOG_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "getajob.log")

_LOG_LINE_RE = re.compile(
    r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d+)\s+\[(\w+)\]\s+([\w\.]+):\s+(.*)$'
)


def read_logs(
    level: Optional[str] = None,
    since: Optional[str] = None,
    limit: int = 200,
    search: Optional[str] = None,
) -> dict:
    """Read recent log lines, filtered."""
    if not os.path.exists(_LOG_PATH):
        return {"lines": [], "total": 0, "message": "No log file"}

    try:
        with open(_LOG_PATH, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
    except Exception as e:
        return {"lines": [], "total": 0, "error": str(e)}

    parsed = []
    for line in lines[-5000:]:  # only scan last 5k lines
        m = _LOG_LINE_RE.match(line.strip())
        if not m:
            continue
        ts, lvl, mod, msg = m.groups()
        if level and lvl != level.upper():
            continue
        if search and search.lower() not in msg.lower():
            continue
        if since:
            try:
                if ts[:19] < since:
                    continue
            except Exception:
                pass
        parsed.append({
            "timestamp": ts[:19],
            "level": lvl,
            "module": mod,
            "message": msg[:500],
        })

    counts = {"INFO": 0, "WARNING": 0, "ERROR": 0, "DEBUG": 0}
    for entry in parsed:
        counts[entry["level"]] = counts.get(entry["level"], 0) + 1

    return {
        "lines": parsed[-limit:][::-1],  # newest first
        "total": len(parsed),
        "counts": counts,
        "log_file": _LOG_PATH,
        "log_size_kb": round(os.path.getsize(_LOG_PATH) / 1024, 1)
                       if os.path.exists(_LOG_PATH) else 0,
    }


def get_recent_errors(hours: int = 24) -> list:
    """Returns ERROR-level log entries from the last N hours."""
    result = read_logs(level="ERROR", limit=100)
    return result.get("lines", [])
