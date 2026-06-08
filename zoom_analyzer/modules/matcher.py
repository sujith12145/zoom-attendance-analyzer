"""
Module: matcher.py
===================
Fuzzy-matching engine:
  1. Exact roll-number match  (highest priority)
  2. Exact name match         (after normalisation)
  3. RapidFuzz token-sort ratio
  4. Levenshtein distance fallback
"""

import re
import pandas as pd
import numpy as np
from rapidfuzz import process, fuzz
from Levenshtein import distance as lev_distance
from typing import Optional, Tuple

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import FUZZY_SCORE_CUTOFF


# ─────────────────────────────────────────────────────────────────────────────

def match_participant(
    participant_name: str,
    name_clean: str,
    roll_in_name: Optional[str],
    master_df: pd.DataFrame,
    score_cutoff: int = FUZZY_SCORE_CUTOFF,
) -> Tuple[Optional[str], Optional[str], str, float]:
    """
    Match a single Zoom participant to a master-list student.

    Parameters
    ----------
    participant_name : raw display name from Zoom
    name_clean       : normalised lowercase version
    roll_in_name     : roll number extracted from display name (or None)
    master_df        : DataFrame with columns [roll_number, name, name_clean]
    score_cutoff     : minimum fuzzy score (0-100) to accept a match

    Returns
    -------
    (roll_number, matched_name, match_method, match_score)
    """

    # ── 1. Roll-number exact match ────────────────────────────────────────
    if roll_in_name:
        mask = master_df['roll_number'].str.upper() == roll_in_name.upper()
        if mask.any():
            row = master_df[mask].iloc[0]
            return row['roll_number'], row['name'], 'roll_exact', 100.0

    # ── 2. Exact name match (normalised) ─────────────────────────────────
    mask = master_df['name_clean'] == name_clean
    if mask.any():
        row = master_df[mask].iloc[0]
        return row['roll_number'], row['name'], 'name_exact', 100.0

    # ── 3. RapidFuzz token_sort_ratio ─────────────────────────────────────
    choices = master_df['name_clean'].tolist()
    result  = process.extractOne(
        name_clean,
        choices,
        scorer=fuzz.token_sort_ratio,
        score_cutoff=score_cutoff,
    )
    if result:
        best_name_clean, score, idx = result
        row = master_df.iloc[idx]
        return row['roll_number'], row['name'], 'fuzzy_rapidfuzz', float(score)

    # ── 4. Levenshtein fallback ───────────────────────────────────────────
    best_idx, best_dist = _levenshtein_best(name_clean, choices)
    if best_idx is not None:
        max_len = max(len(name_clean), len(choices[best_idx]))
        lev_score = (1 - best_dist / max_len) * 100 if max_len > 0 else 0
        if lev_score >= score_cutoff:
            row = master_df.iloc[best_idx]
            return row['roll_number'], row['name'], 'levenshtein', round(lev_score, 1)

    return None, None, 'unmatched', 0.0


def _levenshtein_best(query: str, choices: list[str]) -> Tuple[Optional[int], int]:
    """Return (index, distance) of the closest match using Levenshtein."""
    if not choices:
        return None, 9999
    best_idx  = 0
    best_dist = lev_distance(query, choices[0])
    for i, c in enumerate(choices[1:], 1):
        d = lev_distance(query, c)
        if d < best_dist:
            best_dist = d
            best_idx  = i
    return best_idx, best_dist


# ─────────────────────────────────────────────────────────────────────────────

def match_all_participants(
    zoom_df: pd.DataFrame,
    master_df: pd.DataFrame,
    score_cutoff: int = FUZZY_SCORE_CUTOFF,
) -> pd.DataFrame:
    """
    Run match_participant for every row in zoom_df.

    Returns zoom_df with extra columns:
        matched_roll, matched_name, match_method, match_score
    """
    results = zoom_df.apply(
        lambda r: pd.Series(
            match_participant(
                r['participant_name'],
                r['name_clean'],
                r['roll_in_name'],
                master_df,
                score_cutoff,
            ),
            index=['matched_roll', 'matched_name', 'match_method', 'match_score'],
        ),
        axis=1,
    )
    return pd.concat([zoom_df, results], axis=1)
