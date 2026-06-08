"""
Page: 03_Attendance_Records.py
================================
Browse and search attendance records class-by-class and student-by-student.
"""

import streamlit as st
import pandas as pd
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.database import (
    load_attendance, load_full_history, get_all_classes, delete_class
)
from modules.attendance_calculator import compute_cumulative_stats, apply_risk_labels
from modules.report_generator import generate_csv, generate_excel, generate_pdf
from config import DEFAULT_GREEN_THRESHOLD, DEFAULT_YELLOW_THRESHOLD


def render():
    from modules.auth import check_authentication
    if not check_authentication():
        st.stop()

    st.title("📊 Attendance Records")

    history_df = load_full_history()
    if history_df.empty:
        st.info("📭 No attendance records yet. Upload a Zoom CSV to get started!")
        return

    # ── Tabs ───────────────────────────────────────────────────────────────
    tab_class, tab_student, tab_manage = st.tabs(
        ["🗓️ By Class", "👤 By Student", "🗑️ Manage Classes"]
    )

    # ── By Class ───────────────────────────────────────────────────────────
    with tab_class:
        classes_df = get_all_classes()
        class_options = classes_df.apply(
            lambda r: f"{r['class_date']}  |  {r['class_name']}", axis=1
        ).tolist()

        selected_label = st.selectbox("Select Class", class_options)
        if selected_label:
            idx = class_options.index(selected_label)
            cid = int(classes_df.iloc[idx]['class_id'])
            class_df = load_attendance(class_id=cid)

            enrolled = class_df[class_df['status'].isin(['Present', 'Absent'])]
            present  = (enrolled['status'] == 'Present').sum()
            absent   = (enrolled['status'] == 'Absent').sum()
            pct      = round(present / len(enrolled) * 100, 1) if len(enrolled) else 0

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Total", len(enrolled))
            c2.metric("Present", present)
            c3.metric("Absent", absent)
            c4.metric("Attendance %", f"{pct}%")

            # Filter
            status_filter = st.selectbox("Filter", ['All', 'Present', 'Absent'], key='cf')
            show = enrolled if status_filter == 'All' else enrolled[enrolled['status'] == status_filter]

            disp = ['roll_number', 'name', 'total_minutes', 'sessions', 'status', 'match_method']
            disp = [c for c in disp if c in show.columns]
            st.dataframe(
                show[disp].style.apply(_status_style, axis=1),
                use_container_width=True, height=420,
            )

            # Download row
            d1, d2, d3, _ = st.columns([1, 1, 1, 2])
            with d1:
                st.download_button("⬇️ CSV",
                    data=generate_csv(show[disp]),
                    file_name=f"attendance_{cid}.csv",
                    mime="text/csv",
                    use_container_width=True)
            with d2:
                st.download_button("⬇️ Excel",
                    data=generate_excel(show[disp]),
                    file_name=f"attendance_{cid}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True)
            with d3:
                try:
                    summary = {
                        'Class': selected_label,
                        'Present': present,
                        'Absent': absent,
                        'Attendance %': f"{pct}%",
                    }
                    st.download_button("⬇️ PDF",
                        data=generate_pdf(show[disp], class_name=selected_label,
                                          class_date='', summary=summary),
                        file_name=f"attendance_{cid}.pdf",
                        mime="application/pdf",
                        use_container_width=True)
                except Exception:
                    st.button("⬇️ PDF (unavailable)", disabled=True, use_container_width=True)

    # ── By Student ─────────────────────────────────────────────────────────
    with tab_student:
        cum_df = compute_cumulative_stats(history_df)
        cum_df = apply_risk_labels(cum_df, DEFAULT_GREEN_THRESHOLD, DEFAULT_YELLOW_THRESHOLD)

        search = st.text_input("🔍 Search student (name or roll number)")
        if search:
            mask   = (cum_df['name'].str.contains(search, case=False, na=False) |
                      cum_df['roll_number'].str.contains(search, case=False, na=False))
            cum_df = cum_df[mask]

        st.dataframe(
            cum_df.style.apply(_pct_style, axis=1),
            use_container_width=True, height=460,
        )

        # Individual student drill-down
        st.subheader("🔎 Student Timeline")
        all_names = sorted(history_df['name'].dropna().unique().tolist())
        selected_student = st.selectbox("Select student", ["— Select —"] + all_names)
        if selected_student != "— Select —":
            stu_history = history_df[history_df['name'] == selected_student].sort_values('class_date')
            _show_student_timeline(stu_history)

        # Download cumulative
        st.divider()
        d1, d2 = st.columns(2)
        with d1:
            st.download_button("⬇️ Cumulative CSV",
                data=generate_csv(cum_df),
                file_name="cumulative_attendance.csv",
                mime="text/csv")
        with d2:
            st.download_button("⬇️ Cumulative Excel",
                data=generate_excel(cum_df),
                file_name="cumulative_attendance.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    # ── Manage ─────────────────────────────────────────────────────────────
    with tab_manage:
        st.warning("⚠️ Deleting a class will permanently remove its attendance records.")
        classes_df = get_all_classes()
        st.dataframe(classes_df, use_container_width=True, hide_index=True)

        class_to_delete = st.selectbox(
            "Select class to delete",
            ["— Select —"] + classes_df.apply(
                lambda r: f"[{r['class_id']}] {r['class_date']} | {r['class_name']}", axis=1
            ).tolist(),
        )
        if class_to_delete != "— Select —":
            cid_del = int(class_to_delete.split(']')[0].lstrip('['))
            if st.button(f"🗑️ Delete selected class", type="primary"):
                delete_class(cid_del)
                st.success("Deleted successfully.")
                st.rerun()


def _show_student_timeline(stu_df: pd.DataFrame):
    if stu_df.empty:
        st.info("No records.")
        return
    cols = ['class_date', 'class_name', 'total_minutes', 'sessions', 'status']
    cols = [c for c in cols if c in stu_df.columns]
    st.dataframe(
        stu_df[cols].style.apply(_status_style, axis=1),
        use_container_width=True, height=300,
    )
    present = (stu_df['status'] == 'Present').sum()
    total   = stu_df['status'].isin(['Present', 'Absent']).sum()
    pct     = round(present / total * 100, 1) if total else 0
    st.metric("Overall Attendance", f"{pct}%", f"{present}/{total} classes")


def _status_style(row):
    if 'status' in row.index:
        v = row['status']
        if v == 'Present':  return ['background-color:#d5f5e3']*len(row)
        if v == 'Absent':   return ['background-color:#fadbd8']*len(row)
    return [''] * len(row)


def _pct_style(row):
    if 'attendance_pct' in row.index:
        try:
            pct = float(row['attendance_pct'])
            if pct >= 75:  return ['background-color:#d5f5e3']*len(row)
            if pct >= 50:  return ['background-color:#fef9e7']*len(row)
            return ['background-color:#fadbd8']*len(row)
        except Exception:
            pass
    return [''] * len(row)


if __name__ == "__main__":
    render()
