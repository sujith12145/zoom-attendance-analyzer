"""
Zoom Attendance Analyzer - Configuration & Constants
====================================================
Central configuration file for all settings, thresholds, and constants.
"""

import os

# ─── Application Info ────────────────────────────────────────────────────────
APP_NAME    = "Zoom Attendance Analyzer"
APP_VERSION = "2.0.0"
APP_ICON    = "🎓"

# ─── Directory Layout ─────────────────────────────────────────────────────────
BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
DATA_DIR    = os.path.join(BASE_DIR, "data")
UPLOAD_DIR  = os.path.join(DATA_DIR, "uploads")
REPORTS_DIR = os.path.join(DATA_DIR, "reports")
DB_DIR      = os.path.join(DATA_DIR, "database")
SAMPLE_DIR  = os.path.join(BASE_DIR, "sample_data")

for _d in [DATA_DIR, UPLOAD_DIR, REPORTS_DIR, DB_DIR, SAMPLE_DIR]:
    os.makedirs(_d, exist_ok=True)

# ─── Database ─────────────────────────────────────────────────────────────────
DB_PATH     = os.path.join(DB_DIR, "attendance.db")
CSV_BACKUP  = os.path.join(DB_DIR, "attendance_backup.csv")

# ─── Attendance Defaults ──────────────────────────────────────────────────────
DEFAULT_MIN_DURATION_MINUTES   = 45      # minutes to be marked Present
DEFAULT_GREEN_THRESHOLD        = 75      # % → Green (Safe)
DEFAULT_YELLOW_THRESHOLD       = 50      # % → Yellow (At-Risk)
# Below YELLOW → Red (Critical)

# ─── Fuzzy-Matching ───────────────────────────────────────────────────────────
FUZZY_SCORE_CUTOFF  = 80   # minimum RapidFuzz score (0-100)
ROLL_NUMBER_PATTERN = r'\b([A-Z]{2,4}[-_]?\d{2,4}[-_]?\d{2,6})\b'   # regex to detect roll nos

# ─── Zoom CSV Column Aliases ──────────────────────────────────────────────────
# Zoom exports vary slightly; we normalise via these candidate names.
ZOOM_NAME_COLS    = ["name (original name)", "name", "participant", "user name", "display name"]
ZOOM_JOIN_COLS    = ["join time", "joined at", "join_time"]
ZOOM_LEAVE_COLS   = ["leave time", "left at", "leave_time"]
ZOOM_DURATION_COLS= ["duration (minutes)", "duration", "time in session (minutes)"]
ZOOM_EMAIL_COLS   = ["email", "user email"]

# ─── Master-List Column Aliases ───────────────────────────────────────────────
MASTER_ROLL_COLS  = ["roll number", "roll no", "roll_no", "rollno", "enrollment", "id", "student id"]
MASTER_NAME_COLS  = ["name", "student name", "full name", "student_name"]

# ─── ML Settings ──────────────────────────────────────────────────────────────
ML_MIN_SESSIONS_FOR_PREDICTION = 3     # need at least this many classes to predict
ML_LOOKBACK_WINDOW             = 5     # rolling window for feature engineering

# ─── Report Settings ─────────────────────────────────────────────────────────
REPORT_LOGO_TEXT = APP_NAME
PDF_FONT_FAMILY  = "Helvetica"

# ─── UI Theme Colours ─────────────────────────────────────────────────────────
COLOR_GREEN  = "#2ecc71"
COLOR_YELLOW = "#f39c12"
COLOR_RED    = "#e74c3c"
COLOR_BLUE   = "#3498db"
COLOR_DARK   = "#2c3e50"
COLOR_LIGHT  = "#ecf0f1"

# ─── SMTP Server Configuration for OTP Emails (Optional) ─────────────────────
SMTP_SERVER   = os.environ.get("SMTP_SERVER", "")
SMTP_PORT     = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER     = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
SMTP_FROM     = os.environ.get("SMTP_FROM", "noreply@zoomattendance.com")

