"""
Module: ml_predictor.py
========================
Machine-learning module for:
  1. Predicting a student's next-class attendance probability
  2. Identifying at-risk students
  3. Forecasting class-level attendance trends
  4. Feature engineering from historical data

Models used:
  • RandomForestClassifier  – individual risk prediction
  • GradientBoostingRegressor – class-level attendance % forecast
  • IsolationForest          – anomaly detection (sudden drop students)
"""

import numpy as np
import pandas as pd
from sklearn.ensemble import (
    RandomForestClassifier,
    GradientBoostingRegressor,
    IsolationForest,
)
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import cross_val_score, train_test_split
from sklearn.metrics import classification_report, mean_absolute_error
import warnings as _warnings
_warnings.filterwarnings('ignore')

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    ML_MIN_SESSIONS_FOR_PREDICTION,
    ML_LOOKBACK_WINDOW,
    DEFAULT_GREEN_THRESHOLD,
    DEFAULT_YELLOW_THRESHOLD,
)


# ─────────────────────────────────────────────────────────────────────────────
# Feature Engineering
# ─────────────────────────────────────────────────────────────────────────────

def build_student_features(history_df: pd.DataFrame) -> pd.DataFrame:
    """
    For each student, build a feature vector from their historical attendance.

    Returns DataFrame with columns:
        roll_number, name, attendance_pct, streak_present, streak_absent,
        last_N_present (rolling), avg_duration, std_duration,
        classes_attended, total_classes, risk_label (target)
    """
    df = history_df[history_df['status'].isin(['Present', 'Absent'])].copy()
    df['date_ord'] = pd.to_datetime(df['class_date'], errors='coerce').map(
        lambda d: d.toordinal() if pd.notna(d) else 0
    )
    df = df.sort_values(['roll_number', 'date_ord'])
    df['present_bin'] = (df['status'] == 'Present').astype(int)

    records = []
    for roll, grp in df.groupby('roll_number'):
        grp = grp.reset_index(drop=True)
        n   = len(grp)
        if n < ML_MIN_SESSIONS_FOR_PREDICTION:
            continue

        pct = grp['present_bin'].mean() * 100

        # Rolling window features
        window = grp['present_bin'].tail(ML_LOOKBACK_WINDOW)
        last_n_present = window.mean()
        last_n_trend   = _trend(window.values)

        # Streaks
        streak_p = _current_streak(grp['present_bin'].values, 1)
        streak_a = _current_streak(grp['present_bin'].values, 0)

        # Duration features
        avg_dur = grp['total_minutes'].mean()
        std_dur = grp['total_minutes'].std(ddof=0)

        # Day-of-week pattern (low attendance on Mondays?)
        grp['dow'] = pd.to_datetime(grp['class_date'], errors='coerce').dt.dayofweek
        most_common_dow = grp['dow'].mode().iloc[0] if not grp['dow'].mode().empty else -1

        records.append({
            'roll_number':     roll,
            'name':            grp['name'].iloc[-1],
            'total_classes':   n,
            'present_count':   int(grp['present_bin'].sum()),
            'attendance_pct':  round(pct, 2),
            'last_n_present':  round(last_n_present, 3),
            'last_n_trend':    round(last_n_trend, 4),
            'streak_present':  streak_p,
            'streak_absent':   streak_a,
            'avg_duration':    round(avg_dur, 2),
            'std_duration':    round(std_dur, 2),
            'most_common_dow': int(most_common_dow),
        })

    feat_df = pd.DataFrame(records)
    if feat_df.empty:
        return feat_df

    # Target label
    def _label(pct):
        if pct >= DEFAULT_GREEN_THRESHOLD:  return 'Green'
        elif pct >= DEFAULT_YELLOW_THRESHOLD: return 'Yellow'
        else: return 'Red'

    feat_df['risk_label'] = feat_df['attendance_pct'].apply(_label)
    return feat_df.reset_index(drop=True)


def _trend(arr):
    """Simple linear regression slope on a small array."""
    if len(arr) < 2:
        return 0.0
    x = np.arange(len(arr), dtype=float)
    slope = np.polyfit(x, arr, 1)[0]
    return float(slope)


def _current_streak(arr, val):
    """Count consecutive trailing `val` entries."""
    count = 0
    for v in reversed(arr):
        if v == val:
            count += 1
        else:
            break
    return count


# ─────────────────────────────────────────────────────────────────────────────
# Individual Risk Predictor (Random Forest)
# ─────────────────────────────────────────────────────────────────────────────

FEATURE_COLS = [
    'total_classes', 'attendance_pct', 'last_n_present',
    'last_n_trend', 'streak_present', 'streak_absent',
    'avg_duration', 'std_duration', 'most_common_dow',
]


class AttendanceRiskPredictor:
    """
    Random Forest classifier that predicts a student's risk level.
    Supports train, predict, and cross-validate.
    """

    def __init__(self):
        self.model   = RandomForestClassifier(
            n_estimators=200,
            max_depth=8,
            min_samples_leaf=2,
            random_state=42,
            class_weight='balanced',
        )
        self.le      = LabelEncoder()
        self.trained = False
        self.feature_importances_: dict = {}
        self.cv_score_: float = 0.0

    def train(self, feat_df: pd.DataFrame) -> dict:
        """Train on feature DataFrame. Returns training metrics."""
        if len(feat_df) < 5:
            return {'error': 'Not enough data to train (need ≥5 students with history).'}

        X = feat_df[FEATURE_COLS].fillna(0).values
        y = self.le.fit_transform(feat_df['risk_label'])

        if len(np.unique(y)) < 2:
            return {'error': 'Need at least 2 risk classes to train.'}

        # Cross-validation
        cv_scores = cross_val_score(self.model, X, y, cv=min(5, len(feat_df)//2), scoring='accuracy')
        self.cv_score_ = float(cv_scores.mean())

        # Final fit on all data
        self.model.fit(X, y)
        self.trained = True

        # Feature importances
        self.feature_importances_ = dict(zip(FEATURE_COLS, self.model.feature_importances_))

        # Train-set accuracy
        y_pred = self.model.predict(X)
        report = classification_report(y, y_pred, target_names=self.le.classes_, output_dict=True)

        return {
            'cv_accuracy':    round(self.cv_score_ * 100, 1),
            'train_accuracy': round(report['accuracy'] * 100, 1),
            'n_samples':      len(feat_df),
            'classes':        list(self.le.classes_),
            'feature_importances': self.feature_importances_,
        }

    def predict(self, feat_df: pd.DataFrame) -> pd.DataFrame:
        """
        Predict risk level and probability for each student.
        Returns feat_df with extra columns: predicted_risk, confidence, risk_probability.
        """
        if not self.trained:
            feat_df = feat_df.copy()
            feat_df['predicted_risk']    = feat_df['risk_label']
            feat_df['confidence']        = 0.0
            feat_df['risk_probability']  = feat_df['attendance_pct'] / 100
            return feat_df

        X = feat_df[FEATURE_COLS].fillna(0).values
        proba      = self.model.predict_proba(X)
        pred_idx   = proba.argmax(axis=1)
        pred_label = self.le.inverse_transform(pred_idx)
        confidence = proba.max(axis=1) * 100

        out = feat_df.copy()
        out['predicted_risk']  = pred_label
        out['confidence']      = confidence.round(1)

        # Probability of "Present next class" – proxy: 1 - P(Red)
        if 'Red' in self.le.classes_:
            red_idx = list(self.le.classes_).index('Red')
            out['risk_probability'] = 1 - proba[:, red_idx]
        else:
            out['risk_probability'] = proba.max(axis=1)

        return out


# ─────────────────────────────────────────────────────────────────────────────
# Class-level Trend Forecaster (Gradient Boosting)
# ─────────────────────────────────────────────────────────────────────────────

class AttendanceTrendForecaster:
    """
    Predicts the expected overall attendance % for upcoming classes
    based on historical class-level aggregates.
    """

    def __init__(self):
        self.model   = GradientBoostingRegressor(
            n_estimators=100, learning_rate=0.1,
            max_depth=4, random_state=42,
        )
        self.trained = False

    def _build_class_features(self, history_df: pd.DataFrame) -> pd.DataFrame:
        df = history_df[history_df['status'].isin(['Present', 'Absent'])].copy()
        class_stats = df.groupby(['class_date', 'class_name']).agg(
            total   =('status', 'count'),
            present =('status', lambda x: (x == 'Present').sum()),
        ).reset_index()
        class_stats['pct'] = class_stats['present'] / class_stats['total'] * 100
        class_stats = class_stats.sort_values('class_date').reset_index(drop=True)

        rows = []
        for i in range(2, len(class_stats)):
            win = class_stats.iloc[max(0, i-5):i]
            rows.append({
                'idx':        i,
                'rolling_avg': win['pct'].mean(),
                'rolling_std': win['pct'].std(ddof=0),
                'trend':       _trend(win['pct'].values),
                'last_pct':    class_stats.iloc[i-1]['pct'],
                'total_students': class_stats.iloc[i]['total'],
                'target':      class_stats.iloc[i]['pct'],
            })
        return pd.DataFrame(rows)

    def train(self, history_df: pd.DataFrame) -> dict:
        feat = self._build_class_features(history_df)
        if len(feat) < 3:
            return {'error': 'Need at least 5 classes to train trend model.'}

        X = feat[['rolling_avg', 'rolling_std', 'trend', 'last_pct', 'total_students']].fillna(0)
        y = feat['target']

        self.model.fit(X, y)
        self.trained = True

        y_pred = self.model.predict(X)
        mae    = mean_absolute_error(y, y_pred)
        return {'mae': round(mae, 2), 'n_classes': len(feat)}

    def forecast(self, history_df: pd.DataFrame, n_ahead: int = 3) -> list[dict]:
        """
        Forecast next `n_ahead` class attendance percentages.
        Returns list of {'class_number': int, 'predicted_pct': float}.
        """
        if not self.trained:
            return []

        df = history_df[history_df['status'].isin(['Present', 'Absent'])].copy()
        class_stats = df.groupby(['class_date']).agg(
            total  =('status', 'count'),
            present=('status', lambda x: (x == 'Present').sum()),
        ).reset_index()
        class_stats['pct'] = class_stats['present'] / class_stats['total'] * 100
        class_stats = class_stats.sort_values('class_date').reset_index(drop=True)

        pct_history = class_stats['pct'].tolist()
        total_avg   = class_stats['total'].mean()
        results = []

        for step in range(n_ahead):
            win    = pct_history[max(0, len(pct_history)-5):]
            X_pred = np.array([[
                np.mean(win),
                np.std(win) if len(win) > 1 else 0,
                _trend(np.array(win)),
                pct_history[-1],
                total_avg,
            ]])
            pred = float(np.clip(self.model.predict(X_pred)[0], 0, 100))
            results.append({
                'class_number': len(pct_history) + step + 1,
                'predicted_pct': round(pred, 1),
            })
            pct_history.append(pred)  # auto-regressive

        return results


# ─────────────────────────────────────────────────────────────────────────────
# Anomaly Detection (IsolationForest)
# ─────────────────────────────────────────────────────────────────────────────

def detect_sudden_droppers(history_df: pd.DataFrame) -> pd.DataFrame:
    """
    Use IsolationForest to find students with anomalously low recent attendance
    compared to their own historical baseline.

    Returns DataFrame of anomalous students with an 'anomaly_score' column.
    """
    feat_df = build_student_features(history_df)
    if len(feat_df) < 5:
        return pd.DataFrame()

    X = feat_df[['attendance_pct', 'last_n_present', 'last_n_trend',
                  'streak_absent', 'avg_duration']].fillna(0)

    iso = IsolationForest(contamination=0.15, random_state=42)
    feat_df['anomaly'] = iso.fit_predict(X)          # -1 = anomaly
    feat_df['anomaly_score'] = iso.decision_function(X)  # lower → more anomalous

    anomalies = feat_df[feat_df['anomaly'] == -1].copy()
    anomalies = anomalies.sort_values('anomaly_score')
    return anomalies[['roll_number', 'name', 'attendance_pct', 'last_n_present',
                       'streak_absent', 'avg_duration', 'anomaly_score']].reset_index(drop=True)


# ─────────────────────────────────────────────────────────────────────────────
# Convenience wrapper
# ─────────────────────────────────────────────────────────────────────────────

def run_full_ml_pipeline(history_df: pd.DataFrame) -> dict:
    """
    Runs all ML tasks and returns a results dict with keys:
        features, risk_predictions, train_metrics,
        forecast, anomalies, trend_train_metrics
    """
    results = {}

    feat_df = build_student_features(history_df)
    results['features'] = feat_df

    # Risk predictor
    predictor = AttendanceRiskPredictor()
    train_metrics = predictor.train(feat_df)
    results['train_metrics'] = train_metrics

    if feat_df is not None and not feat_df.empty and 'error' not in train_metrics:
        risk_pred = predictor.predict(feat_df)
    else:
        risk_pred = feat_df.copy() if feat_df is not None else pd.DataFrame()
    results['risk_predictions'] = risk_pred

    # Trend forecaster
    forecaster = AttendanceTrendForecaster()
    trend_metrics = forecaster.train(history_df)
    results['trend_train_metrics'] = trend_metrics
    results['forecast']            = forecaster.forecast(history_df, n_ahead=3)

    # Anomaly detection
    results['anomalies'] = detect_sudden_droppers(history_df)

    return results
