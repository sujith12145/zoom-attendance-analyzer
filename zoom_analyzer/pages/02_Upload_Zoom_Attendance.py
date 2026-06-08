"""
Page: 02_Upload_Zoom_Attendance.py
====================================
Upload Zoom participant CSV reports, process them, and save results.
"""

import streamlit as st
import pandas as pd
from datetime import date
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.attendance_calculator import process_zoom_file
from modules.database import (
    load_master_list_db, master_list_exists,
    insert_class, save_attendance, class_exists, get_class_id,
    get_all_classes,
)
from config import DEFAULT_MIN_DURATION_MINUTES, FUZZY_SCORE_CUTOFF


def render():
    st.title("📤 Upload Zoom Attendance")
    st.markdown("Upload the participant report downloaded from Zoom after each class.")

    # ── Guard: master list required ────────────────────────────────────────
    if not master_list_exists():
        st.error("⚠️ No master student list found! Please upload it first on the **Master List** page.")
        return

    master_df = load_master_list_db()

    # ── Settings sidebar ───────────────────────────────────────────────────
    with st.sidebar:
        st.header("⚙️ Processing Settings")
        min_duration = st.number_input(
            "Min. Duration for Present (minutes)",
            min_value=1, max_value=180,
            value=DEFAULT_MIN_DURATION_MINUTES,
            step=5,
            help="Students attending for this duration or more will be marked Present.",
        )
        fuzzy_cutoff = st.slider(
            "Fuzzy Match Score Cutoff",
            min_value=50, max_value=100,
            value=FUZZY_SCORE_CUTOFF,
            step=5,
            help="Minimum similarity score (0–100) required to match a Zoom name to a student.",
        )
        st.info(f"👥 {len(master_df)} students in master list")

    # ── Upload form ────────────────────────────────────────────────────────
    st.subheader("Class Details")
    col1, col2, col3 = st.columns([2, 1, 2])

    with col1:
        class_name = st.text_input("Class / Subject Name", value="Python Programming",
                                   help="e.g. 'Data Structures – Lecture 5'")
    with col2:
        class_date = st.date_input("Class Date", value=date.today())
    with col3:
        subject_notes = st.text_input("Notes (optional)", placeholder="Topic covered…")

    st.subheader("Upload Zoom CSV")
    zoom_file = st.file_uploader(
        "Zoom Participant Report (CSV or XLSX)",
        type=['csv', 'xlsx', 'xls'],
        help="Download from: Zoom → Reports → Usage → Participants",
    )

    if zoom_file and class_name:
        st.divider()

        # ── Check for duplicate ────────────────────────────────────────────
        date_str = class_date.strftime('%Y-%m-%d')
        if class_exists(class_name, date_str):
            st.warning(f"⚠️ A class named **{class_name}** on **{date_str}** already exists in the database.")
            overwrite = st.checkbox("Overwrite existing record?")
            if not overwrite:
                st.info("Uncheck to keep existing or check to overwrite.")
                return

        try:
            with st.spinner("🔄 Processing attendance…"):
                attendance_df, unmatched_df, warnings = process_zoom_file(
                    zoom_file,
                    master_df,
                    min_duration=min_duration,
                    class_date=date_str,
                    class_name=class_name,
                    score_cutoff=fuzzy_cutoff,
                )

            for w in warnings:
                st.warning(w)

            # ── Metrics row ────────────────────────────────────────────────
            enrolled = attendance_df[attendance_df['status'].isin(['Present', 'Absent'])]
            present  = (enrolled['status'] == 'Present').sum()
            absent   = (enrolled['status'] == 'Absent').sum()
            pct      = round(present / len(enrolled) * 100, 1) if len(enrolled) else 0

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Total Students",   len(enrolled))
            m2.metric("Present",          present,  delta=f"{pct}%")
            m3.metric("Absent",           absent,   delta=f"-{100-pct:.1f}%", delta_color="inverse")
            m4.metric("Attendance %",     f"{pct}%")

            # ── Tabs ───────────────────────────────────────────────────────
            tab_att, tab_unmatched, tab_raw = st.tabs(
                ["✅ Attendance Results", "❓ Unmatched Participants", "🔬 Raw Data"]
            )

            with tab_att:
                _display_attendance_table(attendance_df)

            with tab_unmatched:
                if unmatched_df.empty:
                    st.success("🎉 All Zoom participants were matched to the master list!")
                else:
                    st.warning(f"⚠️ {len(unmatched_df)} participant(s) could NOT be matched.")
                    st.dataframe(unmatched_df, use_container_width=True)
                    st.markdown("""
**Possible reasons:**
- Name was too different from the master list
- A guest / non-student joined the meeting
- Roll number format doesn't match

**Fix:** Manually correct names in the Zoom CSV and re-upload.
                    """)

            with tab_raw:
                st.dataframe(attendance_df, use_container_width=True)

            # ── Save button ────────────────────────────────────────────────
            st.divider()
            col_save, col_cancel = st.columns([1, 3])
            with col_save:
                if st.button("💾 Save to Database", type="primary", use_container_width=True):
                    # If overwrite, delete old record first
                    if class_exists(class_name, date_str):
                        old_id = get_class_id(class_name, date_str)
                        if old_id:
                            from modules.database import delete_class
                            delete_class(old_id)

                    class_id = insert_class(class_name, date_str, subject="", notes=subject_notes)
                    n_saved  = save_attendance(attendance_df, class_id)
                    st.success(f"✅ Saved **{n_saved} records** for **{class_name}** ({date_str})")
                    st.balloons()

        except ValueError as e:
            st.error(f"❌ {e}")
        except Exception as e:
            st.error(f"❌ Unexpected error: {e}")
            import traceback; st.code(traceback.format_exc())

    # ── Past uploads ───────────────────────────────────────────────────────
    st.divider()
    st.subheader("📚 Past Uploads")
    classes_df = get_all_classes()
    if classes_df.empty:
        st.info("No classes uploaded yet.")
    else:
        st.dataframe(classes_df, use_container_width=True, hide_index=True)


def _display_attendance_table(df: pd.DataFrame):
    """Display styled attendance table."""
    status_filter = st.selectbox(
        "Filter by status", ['All', 'Present', 'Absent', 'Unmatched'], index=0
    )

    filtered = df if status_filter == 'All' else df[df['status'] == status_filter]

    def _style_row(row):
        color_map = {'Present': '#d5f5e3', 'Absent': '#fadbd8', 'Unmatched': '#fef9e7'}
        bg = color_map.get(row['status'], '')
        return [f'background-color: {bg}'] * len(row)

    disp_cols = ['roll_number', 'name', 'total_minutes', 'sessions', 'status', 'match_method', 'match_score']
    disp_cols = [c for c in disp_cols if c in filtered.columns]
    st.dataframe(
        filtered[disp_cols].style.apply(_style_row, axis=1),
        use_container_width=True,
        height=400,
    )
    st.caption(f"Showing {len(filtered)} of {len(df)} rows")


if __name__ == "__main__":
    render()
