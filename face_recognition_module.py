"""
attendance_module.py
────────────────────
Handles:
  - Student data persistence  (students.json)
  - Attendance record persistence (records.json)
  - Helper utilities: today's date, current time
  - Core business logic: add / remove student, mark present / absent,
    mark remaining absent, export CSV

Usage:
    from modules.attendance_module import (
        students, records, face_db,
        add_student, remove_student, mark_attendance,
        mark_remaining_absent, export_csv,
        today_str, time_str,
    )
"""

import os
import csv
import json
from datetime import datetime

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR      = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STUDENTS_FILE = os.path.join(BASE_DIR, "data", "students.json")
RECORDS_FILE  = os.path.join(BASE_DIR, "data", "records.json")

# ── Date / time helpers ───────────────────────────────────────────────────────

def today_str() -> str:
    """Return today's date as 'YYYY-MM-DD'."""
    return datetime.now().strftime("%Y-%m-%d")


def time_str() -> str:
    """Return current time as 'HH:MM:SS'."""
    return datetime.now().strftime("%H:%M:%S")


# ── JSON persistence ──────────────────────────────────────────────────────────

def _load_json(path: str, default):
    """Load JSON from *path*, returning *default* if the file doesn't exist."""
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default


def _save_json(path: str, data) -> None:
    """Write *data* as pretty-printed JSON to *path*, creating dirs as needed."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ── In-memory state (mutable lists shared across the app) ────────────────────
#    Import these directly; they are updated in-place by the functions below.

students: list = _load_json(STUDENTS_FILE, [])
records:  list = _load_json(RECORDS_FILE,  [])


def _save_all() -> None:
    """Flush both in-memory lists to disk."""
    _save_json(STUDENTS_FILE, students)
    _save_json(RECORDS_FILE,  records)


# ── Student management ────────────────────────────────────────────────────────

def add_student(name: str, roll: str = "") -> dict | None:
    """Register a new student.

    Args:
        name: Full name (must be unique, case-insensitive).
        roll: Roll number string.  Auto-assigned if empty.

    Returns:
        The newly created student dict, or None if *name* already exists.

    Student dict schema:
        { "id": str, "name": str, "roll": str, "date": str }
    """
    name = name.strip()
    if not name:
        return None
    if any(s["name"].lower() == name.lower() for s in students):
        return None                                     # duplicate

    sid  = str(int(datetime.now().timestamp() * 1000))
    roll = roll.strip() or str(len(students) + 1)
    student = {"id": sid, "name": name, "roll": roll, "date": today_str()}
    students.append(student)
    _save_all()
    return student


def remove_student(sid: str, face_db: dict) -> bool:
    """Remove a student and all their attendance records.

    Also removes their face embeddings from *face_db* (in-place).
    Caller is responsible for calling save_faces(face_db) afterwards.

    Args:
        sid:      Student ID to remove.
        face_db:  Live face-embedding database (mutated in-place).

    Returns:
        True if the student was found and removed, False otherwise.
    """
    global students, records

    if not any(s["id"] == sid for s in students):
        return False

    students = [s for s in students if s["id"] != sid]
    records  = [r for r in records  if r["studentId"] != sid]
    face_db.pop(sid, None)
    _save_all()
    return True


# ── Attendance logic ──────────────────────────────────────────────────────────

def mark_attendance(sid: str, status: str) -> dict | None:
    """Create or update an attendance record for today.

    If the student already has a record for today it is overwritten
    (useful when re-marking).

    Args:
        sid:    Student ID.
        status: "present" or "absent".

    Returns:
        The record dict, or None if student not found.

    Record dict schema:
        { "studentId", "studentName", "roll", "date", "status", "time" }
    """
    student = next((s for s in students if s["id"] == sid), None)
    if not student:
        return None

    today = today_str()
    entry = {
        "studentId":   sid,
        "studentName": student["name"],
        "roll":        student["roll"],
        "date":        today,
        "status":      status,
        "time":        time_str(),
    }

    existing_idx = next(
        (i for i, r in enumerate(records) if r["studentId"] == sid and r["date"] == today),
        None,
    )
    if existing_idx is not None:
        records[existing_idx] = entry
    else:
        records.append(entry)

    _save_all()
    return entry


def mark_remaining_absent() -> list:
    """Mark every student who hasn't been marked today as absent.

    Returns:
        List of student dicts that were marked absent.
    """
    today      = today_str()
    marked_ids = {r["studentId"] for r in records if r["date"] == today}
    unmarked   = [s for s in students if s["id"] not in marked_ids]

    for s in unmarked:
        mark_attendance(s["id"], "absent")

    return unmarked


# ── Export ────────────────────────────────────────────────────────────────────

def export_csv(output_path: str | None = None) -> str:
    """Export all records to a CSV file.

    Args:
        output_path: Full file path for the CSV.
                     Defaults to  <project_root>/attendance_YYYY-MM-DD.csv

    Returns:
        The absolute path of the file that was written.

    Raises:
        ValueError: If there are no records to export.
    """
    if not records:
        raise ValueError("No records to export.")

    if output_path is None:
        output_path = os.path.join(BASE_DIR, f"attendance_{today_str()}.csv")

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Date", "Roll No.", "Student Name", "Status", "Time"])
        for r in sorted(records, key=lambda x: (x["date"], x["roll"])):
            writer.writerow([
                r["date"],
                r["roll"],
                r["studentName"],
                r["status"].capitalize(),
                r.get("time", ""),
            ])

    return output_path


# ── Query helpers ─────────────────────────────────────────────────────────────

def today_records() -> list:
    """Return all attendance records for today."""
    return [r for r in records if r["date"] == today_str()]


def attendance_stats() -> dict:
    """Return a summary dict for today's attendance.

    Returns:
        {
          "total":    int,   # total registered students
          "present":  int,
          "absent":   int,
          "rate_pct": int,   # 0-100
        }
    """
    today     = today_str()
    present_n = sum(1 for r in records if r["date"] == today and r["status"] == "present")
    absent_n  = sum(1 for r in records if r["date"] == today and r["status"] == "absent")
    total     = len(students)
    rate      = round(present_n / total * 100) if total else 0

    return {
        "total":    total,
        "present":  present_n,
        "absent":   absent_n,
        "rate_pct": rate,
    }
