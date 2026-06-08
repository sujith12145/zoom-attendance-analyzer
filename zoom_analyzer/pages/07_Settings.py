"""
Page: 07_Settings.py
======================
Application settings: thresholds, database management, sample data.
"""

import streamlit as st
import pandas as pd
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.database import get_attendance_summary, export_csv_backup, reset_database
from config import (
    APP_NAME, APP_VERSION,
    DEFAULT_MIN_DURATION_MINUTES,
    DEFAULT_GREEN_THRESHOLD, DEFAULT_YELLOW_THRESHOLD,
    FUZZY_SCORE_CUTOFF, DB_PATH,
)


def render():
    st.title("⚙️ Settings")

    # ── App info ───────────────────────────────────────────────────────────
    with st.expander("ℹ️ Application Info", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**Application:** {APP_NAME}")
            st.markdown(f"**Version:** {APP_VERSION}")
            st.markdown(f"**Database:** `{DB_PATH}`")
        with col2:
            summ = get_attendance_summary()
            st.metric("Total Students",  summ['total_students'])
            st.metric("Total Classes",   summ['total_classes'])
            st.metric("Total Records",   summ['total_records'])

    st.divider()

    # ── Default threshold settings ─────────────────────────────────────────
    st.subheader("🎛️ Default Threshold Configuration")
    st.info("These are **default** values. You can override them per-upload on the Upload page "
            "and per-analysis on the Analytics page.")

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        st.metric("Min Duration (Present)", f"{DEFAULT_MIN_DURATION_MINUTES} min",
                  help="Change via the Upload Zoom page sidebar")
    with col_b:
        st.metric("Green Threshold",  f"{DEFAULT_GREEN_THRESHOLD}%",
                  help="Change via the Analytics page sidebar")
    with col_c:
        st.metric("Yellow Threshold", f"{DEFAULT_YELLOW_THRESHOLD}%",
                  help="Change via the Analytics page sidebar")

    st.markdown("""
> **To permanently change defaults**, edit `config.py`:
> ```python
> DEFAULT_MIN_DURATION_MINUTES = 45    # Change this
> DEFAULT_GREEN_THRESHOLD      = 75    # Change this
> DEFAULT_YELLOW_THRESHOLD     = 50    # Change this
> FUZZY_SCORE_CUTOFF           = 80    # Change this
> ```
    """)

    st.divider()

    # ── Database management ────────────────────────────────────────────────
    st.subheader("🗄️ Database Management")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("**Backup Database**")
        if st.button("💾 Export CSV Backup", use_container_width=True):
            path = export_csv_backup()
            st.success(f"Backup saved to: `{path}`")
            # Also provide download
            with open(path, 'rb') as f:
                st.download_button("⬇️ Download Backup",
                    data=f.read(), file_name="attendance_backup.csv",
                    mime="text/csv")

    with col2:
        st.markdown("**Database Stats**")
        st.info(f"""
- Students: {summ['total_students']}
- Classes:  {summ['total_classes']}
- Records:  {summ['total_records']}
- Avg Att.: {summ['avg_attendance_pct']}%
        """)

    with col3:
        st.markdown("**⚠️ Danger Zone**")
        if st.checkbox("I understand this will delete ALL data"):
            if st.button("🗑️ Reset Database", type="primary", use_container_width=True):
                reset_database()
                st.success("Database reset! All data has been cleared.")
                st.rerun()

    st.divider()

    # ── Zoom CSV format guide ──────────────────────────────────────────────
    st.subheader("📖 Zoom CSV Format Guide")
    st.markdown("""
### How to export the participant report from Zoom

1. Sign in to **Zoom Web Portal** (zoom.us)
2. Go to **Reports → Usage**
3. Select the meeting → click **Participants**
4. Click **Export with meeting data** or **Export as CSV**

### Expected columns (auto-detected):

| Column Name             | Alias Accepted                    |
|-------------------------|-----------------------------------|
| `Name (Original Name)`  | `name`, `participant`, `user name` |
| `Join Time`             | `joined at`, `join_time`           |
| `Leave Time`            | `left at`, `leave_time`            |
| `Duration (Minutes)`    | `duration`, `time in session`      |
| `User Email`            | `email`                            |

### Name Matching Priority:
1. 🔢 **Roll number in display name** (e.g., `CS-21-045 John Doe`)
2. ✅ **Exact name match** (case-insensitive)
3. 🔍 **RapidFuzz token sort ratio** (threshold: {cutoff}%)
4. 📏 **Levenshtein distance fallback**

### Multi-session handling:
If a student joins/leaves multiple times, all sessions are **merged** and durations summed.
    """.format(cutoff=FUZZY_SCORE_CUTOFF))

    st.divider()

    # ── Sample data ────────────────────────────────────────────────────────
    st.subheader("🧪 Sample Data")
    st.markdown("Use the sample data generator to create test datasets.")
    st.code("cd zoom_analyzer && python generate_sample_data.py", language="bash")
    st.markdown("This creates `sample_data/` with:")
    st.markdown("""
- `sample_master_list.csv` – 50 students
- `sample_zoom_class1.csv` through `sample_zoom_class5.csv` – 5 class sessions
    """)

    # ── Module architecture ────────────────────────────────────────────────
    with st.expander("🏗️ Module Architecture"):
        st.markdown("""
```
zoom_analyzer/
│
├── app.py                    # Main Streamlit entry point
├── config.py                 # All constants & settings
├── requirements.txt          # Python dependencies
├── generate_sample_data.py   # Sample data generator
│
├── modules/
│   ├── preprocessor.py       # Data cleaning & normalisation
│   ├── matcher.py            # Fuzzy name matching
│   ├── attendance_calculator.py  # Core attendance logic
│   ├── analytics.py          # Plotly chart builders
│   ├── ml_predictor.py       # ML models (RF, GB, IF)
│   ├── report_generator.py   # CSV / Excel / PDF export
│   └── database.py           # SQLite persistence
│
├── pages/
│   ├── 01_Upload_Master_List.py
│   ├── 02_Upload_Zoom_Attendance.py
│   ├── 03_Attendance_Records.py
│   ├── 04_Analytics.py
│   ├── 05_ML_Predictions.py
│   ├── 06_Reports.py
│   └── 07_Settings.py
│
├── data/
│   ├── database/attendance.db
│   └── reports/
│
└── sample_data/
    ├── sample_master_list.csv
    └── sample_zoom_class*.csv
```
        """)


if __name__ == "__main__":
    render()
