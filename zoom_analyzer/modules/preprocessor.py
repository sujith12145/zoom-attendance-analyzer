"""
Module: preprocessor.py
========================
Handles all data-cleaning and normalisation tasks:
  • Master student list ingestion
  • Zoom CSV ingestion  
  • Name / roll-number normalisation
  • Duplicate removal
"""

import re
import io
import pandas as pd
import numpy as np
from typing import Optional, Tuple

from config import (
    ZOOM_NAME_COLS, ZOOM_JOIN_COLS, ZOOM_LEAVE_COLS,
    ZOOM_DURATION_COLS, ZOOM_EMAIL_COLS,
    MASTER_ROLL_COLS, MASTER_NAME_COLS,
    ROLL_NUMBER_PATTERN,
)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _lower_strip(s: str) -> str:
    """Lowercase, strip whitespace, collapse inner spaces."""
    return re.sub(r'\s+', ' ', str(s).strip().lower())


def _normalise_col(df: pd.DataFrame, candidates: list[str]) -> Optional[str]:
    """Return the first column name in *df* that matches a candidate (case-insensitive)."""
    norm_cols = {c.lower().strip(): c for c in df.columns}
    for cand in candidates:
        if cand.lower() in norm_cols:
            return norm_cols[cand.lower()]
    return None


def clean_name(name: str) -> str:
    """
    Normalise a display name:
      1. Strip leading/trailing whitespace
      2. Remove special chars except hyphens, dots, apostrophes
      3. Collapse multiple spaces
      4. Title-case
    """
    name = str(name).strip()
    name = re.sub(r'[^\w\s\-\.\']', ' ', name)   # keep hyphens, dots, apostrophes
    name = re.sub(r'\s+', ' ', name).strip()
    return name.title()


def clean_roll_number(roll: str) -> str:
    """Upper-case roll number and remove spaces/underscores around separators."""
    roll = str(roll).strip().upper()
    roll = re.sub(r'\s+', '', roll)
    return roll


def extract_roll_from_name(display_name: str) -> Optional[str]:
    """
    Try to find a roll number embedded in a Zoom display name.
    e.g. "CS-21-045 John Doe"  →  "CS-21-045"
    """
    match = re.search(ROLL_NUMBER_PATTERN, display_name.upper())
    return match.group(1) if match else None


# ─────────────────────────────────────────────────────────────────────────────
# Master-list loader
# ─────────────────────────────────────────────────────────────────────────────

def load_master_list(file_obj) -> Tuple[pd.DataFrame, list[str]]:
    """
    Load and clean a master student-list CSV/Excel.

    Returns
    -------
    df      : cleaned DataFrame with columns ['roll_number', 'name', 'name_clean']
    warnings: list of warning strings
    """
    warnings: list[str] = []

    # ── Read file ──────────────────────────────────────────────────────────
    filename = getattr(file_obj, 'name', '').lower()
    try:
        if filename.endswith('.xlsx') or filename.endswith('.xls'):
            df = pd.read_excel(file_obj)
        else:
            raw = file_obj.read()
            # Try common encodings
            for enc in ('utf-8', 'utf-8-sig', 'latin-1', 'cp1252'):
                try:
                    df = pd.read_csv(io.BytesIO(raw), encoding=enc)
                    break
                except Exception:
                    continue
            else:
                raise ValueError("Could not decode the CSV file.")
    except Exception as e:
        raise ValueError(f"Failed to read master list: {e}")

    # ── Detect columns ─────────────────────────────────────────────────────
    roll_col = _normalise_col(df, MASTER_ROLL_COLS)
    name_col = _normalise_col(df, MASTER_NAME_COLS)

    if roll_col is None:
        warnings.append("⚠️ Roll-number column not detected; using row index as roll number.")
        df['roll_number'] = [f"STU{i+1:04d}" for i in range(len(df))]
    else:
        df['roll_number'] = df[roll_col].astype(str).apply(clean_roll_number)

    if name_col is None:
        raise ValueError("Could not detect a 'Name' column in the master list. "
                         "Please ensure a column named 'Name' or 'Student Name' exists.")
    df['name'] = df[name_col].astype(str).apply(clean_name)

    # ── Drop rows with blank name or roll ─────────────────────────────────
    before = len(df)
    df = df[df['name'].str.strip() != ''].copy()
    df = df[df['roll_number'].str.strip() != ''].copy()
    dropped = before - len(df)
    if dropped:
        warnings.append(f"⚠️ Dropped {dropped} rows with blank name or roll number.")

    # ── Duplicates ────────────────────────────────────────────────────────
    dup_roll = df.duplicated('roll_number', keep='first').sum()
    dup_name = df.duplicated('name', keep='first').sum()
    if dup_roll:
        warnings.append(f"⚠️ Removed {dup_roll} duplicate roll numbers.")
    if dup_name:
        warnings.append(f"⚠️ Removed {dup_name} duplicate names.")
    df = df.drop_duplicates('roll_number', keep='first')
    df = df.drop_duplicates('name', keep='first')

    # ── Add normalised name for matching ──────────────────────────────────
    df['name_clean'] = df['name'].str.lower().str.replace(r'[^a-z0-9 ]', ' ', regex=True).str.strip()
    df['name_clean'] = df['name_clean'].str.replace(r'\s+', ' ', regex=True)

    df = df[['roll_number', 'name', 'name_clean']].reset_index(drop=True)
    return df, warnings


# ─────────────────────────────────────────────────────────────────────────────
# Zoom CSV loader
# ─────────────────────────────────────────────────────────────────────────────

def load_zoom_csv(file_obj) -> Tuple[pd.DataFrame, list[str]]:
    """
    Load and pre-process a Zoom participant report CSV.

    Returns
    -------
    df      : cleaned DataFrame with standardised columns
    warnings: list of warning strings

    Output columns:
        participant_name, name_clean, roll_in_name,
        join_time, leave_time, duration_minutes, email (optional)
    """
    warnings: list[str] = []

    # ── Read ──────────────────────────────────────────────────────────────
    filename = getattr(file_obj, 'name', '').lower()
    try:
        if filename.endswith('.xlsx') or filename.endswith('.xls'):
            df = pd.read_excel(file_obj, skiprows=_detect_skip_rows_excel(file_obj))
        else:
            raw = file_obj.read()
            df, skip = _smart_read_zoom_csv(raw)
    except Exception as e:
        raise ValueError(f"Failed to read Zoom CSV: {e}")

    if df is None or df.empty:
        raise ValueError("The uploaded Zoom CSV is empty or unreadable.")

    # ── Detect columns ─────────────────────────────────────────────────────
    name_col     = _normalise_col(df, ZOOM_NAME_COLS)
    join_col     = _normalise_col(df, ZOOM_JOIN_COLS)
    leave_col    = _normalise_col(df, ZOOM_LEAVE_COLS)
    dur_col      = _normalise_col(df, ZOOM_DURATION_COLS)
    email_col    = _normalise_col(df, ZOOM_EMAIL_COLS)

    if name_col is None:
        raise ValueError("Could not detect participant-name column in Zoom CSV. "
                         f"Available columns: {list(df.columns)}")

    # ── Name cleaning ─────────────────────────────────────────────────────
    df['participant_name'] = df[name_col].astype(str).apply(clean_name)
    df['name_clean']       = (
        df['participant_name']
        .str.lower()
        .str.replace(r'[^a-z0-9 ]', ' ', regex=True)
        .str.strip()
        .str.replace(r'\s+', ' ', regex=True)
    )
    df['roll_in_name'] = df['participant_name'].apply(extract_roll_from_name)

    # ── Times ─────────────────────────────────────────────────────────────
    if join_col:
        df['join_time'] = pd.to_datetime(df[join_col], errors='coerce')
    else:
        df['join_time'] = pd.NaT
        warnings.append("⚠️ Join-time column not found.")

    if leave_col:
        df['leave_time'] = pd.to_datetime(df[leave_col], errors='coerce')
    else:
        df['leave_time'] = pd.NaT
        warnings.append("⚠️ Leave-time column not found.")

    # ── Duration ──────────────────────────────────────────────────────────
    if dur_col:
        df['duration_minutes'] = pd.to_numeric(df[dur_col], errors='coerce').fillna(0)
    elif join_col and leave_col:
        diff = (df['leave_time'] - df['join_time']).dt.total_seconds() / 60
        df['duration_minutes'] = diff.clip(lower=0).fillna(0)
        warnings.append("ℹ️ Duration calculated from join/leave times.")
    else:
        df['duration_minutes'] = 0
        warnings.append("⚠️ Neither duration nor join/leave times found; duration set to 0.")

    # ── Email ─────────────────────────────────────────────────────────────
    df['email'] = df[email_col].astype(str).str.lower().str.strip() if email_col else ''

    # ── Drop host / irrelevant rows ────────────────────────────────────────
    before = len(df)
    df = df[df['participant_name'].str.strip() != ''].copy()
    df = df[~df['participant_name'].str.lower().isin(['nan', 'name', 'participant'])]
    dropped = before - len(df)
    if dropped:
        warnings.append(f"ℹ️ Dropped {dropped} empty/header rows from Zoom CSV.")

    out_cols = ['participant_name', 'name_clean', 'roll_in_name',
                'join_time', 'leave_time', 'duration_minutes', 'email']
    return df[out_cols].reset_index(drop=True), warnings


# ─────────────────────────────────────────────────────────────────────────────
# Private helpers
# ─────────────────────────────────────────────────────────────────────────────

def _smart_read_zoom_csv(raw: bytes) -> Tuple[Optional[pd.DataFrame], int]:
    """
    Zoom CSVs often have a metadata header block (meeting info).
    Try reading with different skip_rows until we get a parseable table.
    """
    for enc in ('utf-8', 'utf-8-sig', 'latin-1', 'cp1252'):
        for skip in (0, 1, 2, 3, 4, 5):
            try:
                df = pd.read_csv(io.BytesIO(raw), encoding=enc, skiprows=skip)
                # Heuristic: valid if we have ≥2 columns with ≥1 data row
                if len(df.columns) >= 2 and len(df) >= 1:
                    return df, skip
            except Exception:
                continue
    return None, 0


def _detect_skip_rows_excel(file_obj) -> int:
    """Read first few rows to detect where the actual header is."""
    try:
        probe = pd.read_excel(file_obj, nrows=10, header=None)
        file_obj.seek(0)
        for i, row in probe.iterrows():
            vals = [str(v).lower() for v in row]
            if any(k in vals for k in ['name', 'participant', 'join time', 'duration']):
                return i
    except Exception:
        pass
    return 0
