"""
Module: attendance_calculator.py
==================================
Core logic for:
  • Merging multi-session entries per student
  • Computing total attendance duration
  • Marking Present / Absent per configurable threshold
  • Building per-class and cumulative summary tables
"""

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Optional

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DEFAULT_MIN_DURATION_MINUTES
from modules.preprocessor import load_master_list, load_zoom_csv
from modules.matcher      import match_all_participants


# ─────────────────────────────────────────────────────────────────────────────
# Session merging & duration
# ─────────────────────────────────────────────────────────────────────────────

def merge_sessions(matched_df: pd.DataFrame) -> pd.DataFrame:
    """
    A student may join/leave multiple times in one class.
    Group by matched_roll (or participant_name if unmatched) and sum durations.

    Returns one row per unique student (or unmatched display name).
    """
    def _group_key(row):
        return row['matched_roll'] if pd.notna(row['matched_roll']) else f"__UNMATCHED__{row['participant_name']}"

    matched_df = matched_df.copy()
    matched_df['_group_key'] = matched_df.apply(_group_key, axis=1)

    agg = (
        matched_df
        .groupby('_group_key', as_index=False)
        .agg(
            participant_name =('participant_name',  lambda x: x.iloc[0]),
            matched_roll     =('matched_roll',      'first'),
            matched_name     =('matched_name',      'first'),
            match_method     =('match_method',      'first'),
            match_score      =('match_score',       'max'),
            total_minutes    =('duration_minutes',  'sum'),
            sessions         =('duration_minutes',  'count'),
            first_join       =('join_time',         'min'),
            last_leave       =('leave_time',        'max'),
            email            =('email',             'first'),
        )
    )
    agg = agg.drop(columns=['_group_key'])
    return agg.reset_index(drop=True)


# ─────────────────────────────────────────────────────────────────────────────
# Attendance marking
# ─────────────────────────────────────────────────────────────────────────────

def mark_attendance(
    merged_df: pd.DataFrame,
    master_df: pd.DataFrame,
    min_duration: float = DEFAULT_MIN_DURATION_MINUTES,
    class_date: Optional[str] = None,
    class_name: str = "Class",
) -> pd.DataFrame:
    """
    Join merged Zoom data with the full master list to ensure EVERY student
    appears (absent students would otherwise be missing).

    Parameters
    ----------
    merged_df    : output of merge_sessions()
    master_df    : full master student list
    min_duration : threshold in minutes for Present
    class_date   : ISO date string (YYYY-MM-DD); defaults to today
    class_name   : label for this class / session

    Returns
    -------
    DataFrame with columns:
        roll_number, name, total_minutes, sessions, status,
        match_method, match_score, class_date, class_name
    """
    if class_date is None:
        class_date = datetime.today().strftime('%Y-%m-%d')

    # Start from the full master list so absent students are included
    result = master_df[['roll_number', 'name']].copy()

    # Merge with matched data
    zoom_subset = merged_df[
        merged_df['matched_roll'].notna()
    ][['matched_roll', 'total_minutes', 'sessions', 'match_method', 'match_score']].copy()
    zoom_subset = zoom_subset.rename(columns={'matched_roll': 'roll_number'})

    result = result.merge(zoom_subset, on='roll_number', how='left')
    result['total_minutes'] = result['total_minutes'].fillna(0)
    result['sessions']      = result['sessions'].fillna(0).astype(int)
    result['match_method']  = result['match_method'].fillna('absent')
    result['match_score']   = result['match_score'].fillna(0.0)

    # Mark present / absent
    result['status'] = result['total_minutes'].apply(
        lambda m: 'Present' if m >= min_duration else 'Absent'
    )

    result['class_date']  = class_date
    result['class_name']  = class_name
    result['min_duration_used'] = min_duration

    # Unmatched Zoom participants (guests / unknown names)
    unmatched = merged_df[merged_df['matched_roll'].isna()].copy()
    if not unmatched.empty:
        extra = pd.DataFrame({
            'roll_number'      : unmatched['participant_name'],
            'name'             : unmatched['participant_name'],
            'total_minutes'    : unmatched['total_minutes'],
            'sessions'         : unmatched['sessions'],
            'match_method'     : 'unmatched',
            'match_score'      : 0.0,
            'status'           : 'Unmatched',
            'class_date'       : class_date,
            'class_name'       : class_name,
            'min_duration_used': min_duration,
        })
        result = pd.concat([result, extra], ignore_index=True)

    return result.reset_index(drop=True)


# ─────────────────────────────────────────────────────────────────────────────
# High-level pipeline
# ─────────────────────────────────────────────────────────────────────────────

def process_zoom_file(
    zoom_file,
    master_df: pd.DataFrame,
    min_duration: float = DEFAULT_MIN_DURATION_MINUTES,
    class_date: Optional[str] = None,
    class_name: str = "Class",
    score_cutoff: int = 80,
) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    """
    Full pipeline:  upload → clean → match → merge → mark

    Returns
    -------
    attendance_df   : per-student attendance for this class
    unmatched_df    : Zoom participants that could NOT be matched
    all_warnings    : combined warning messages
    """
    zoom_df, w1   = load_zoom_csv(zoom_file)
    matched_df    = match_all_participants(zoom_df, master_df, score_cutoff)
    merged_df     = merge_sessions(matched_df)
    attendance_df = mark_attendance(merged_df, master_df, min_duration, class_date, class_name)

    unmatched_df = merged_df[merged_df['matched_roll'].isna()][
        ['participant_name', 'total_minutes', 'sessions', 'email']
    ].copy() if 'matched_roll' in merged_df.columns else pd.DataFrame()

    return attendance_df, unmatched_df, w1


# ─────────────────────────────────────────────────────────────────────────────
# Cumulative analytics helpers
# ─────────────────────────────────────────────────────────────────────────────

def compute_cumulative_stats(history_df: pd.DataFrame) -> pd.DataFrame:
    """
    Given the full historical attendance DataFrame (all classes combined),
    compute per-student cumulative stats.

    Input columns required: roll_number, name, status, class_date
    """
    # Only consider enrolled students (not unmatched)
    df = history_df[history_df['status'].isin(['Present', 'Absent'])].copy()

    grp = df.groupby(['roll_number', 'name'], as_index=False).agg(
        total_classes   =('status', 'count'),
        present_count   =('status', lambda x: (x == 'Present').sum()),
        absent_count    =('status', lambda x: (x == 'Absent').sum()),
        avg_duration    =('total_minutes', 'mean'),
        last_seen       =('class_date', 'max'),
    )
    grp['attendance_pct'] = (grp['present_count'] / grp['total_classes'] * 100).round(1)
    return grp.sort_values('attendance_pct', ascending=False).reset_index(drop=True)


def apply_risk_labels(
    cumulative_df: pd.DataFrame,
    green_threshold:  float = 75.0,
    yellow_threshold: float = 50.0,
) -> pd.DataFrame:
    """
    Add a 'risk_level' column:
      attendance_pct >= green_threshold  → Green
      attendance_pct >= yellow_threshold → Yellow
      else                               → Red
    """
    def _risk(pct):
        if pct >= green_threshold:
            return 'Green'
        elif pct >= yellow_threshold:
            return 'Yellow'
        else:
            return 'Red'

    df = cumulative_df.copy()
    df['risk_level'] = df['attendance_pct'].apply(_risk)
    return df
