"""
Page: 06_Reports.py
====================
Generate and download reports in CSV, Excel, and PDF formats.
"""

import streamlit as st
import pandas as pd
from datetime import datetime
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.database                import load_full_history, get_all_classes, load_attendance
from modules.attendance_calculator   import compute_cumulative_stats, apply_risk_labels
from modules.report_generator        import generate_csv, generate_excel, generate_pdf
from config import DEFAULT_GREEN_THRESHOLD, DEFAULT_YELLOW_THRESHOLD


def render():
    from modules.auth import check_authentication
    if not check_authentication():
        st.stop()

    st.title("📄 Reports & Downloads")
    st.markdown("Generate formatted reports in **CSV**, **Excel**, and **PDF** formats.")

    history_df = load_full_history()
    if history_df.empty:
        st.info("No data available. Upload attendance records first.")
        return

    cum_df     = compute_cumulative_stats(history_df)
    cum_df     = apply_risk_labels(cum_df, DEFAULT_GREEN_THRESHOLD, DEFAULT_YELLOW_THRESHOLD)
    classes_df = get_all_classes()
    ts         = datetime.now().strftime("%Y%m%d_%H%M%S")

    # ── Report type selection ──────────────────────────────────────────────
    report_type = st.radio(
        "Select report type",
        ["📊 Cumulative Summary", "🗓️ Single Class Report", "📚 Full History Export"],
        horizontal=True,
    )

    st.divider()

    # ── Cumulative Summary ─────────────────────────────────────────────────
    if report_type == "📊 Cumulative Summary":
        st.subheader("Cumulative Attendance Summary")
        st.dataframe(cum_df, use_container_width=True, hide_index=True)

        c1, c2, c3 = st.columns(3)
        with c1:
            st.download_button(
                "⬇️ Download CSV",
                data=generate_csv(cum_df),
                file_name=f"cumulative_summary_{ts}.csv",
                mime="text/csv",
                use_container_width=True,
            )
        with c2:
            excel_bytes = generate_excel(
                cum_df,
                cumulative_df=cum_df,
                history_df=history_df,
                title="Cumulative Attendance Report",
            )
            st.download_button(
                "⬇️ Download Excel",
                data=excel_bytes,
                file_name=f"cumulative_summary_{ts}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
        with c3:
            try:
                summary = {
                    'Generated'   : datetime.now().strftime('%Y-%m-%d %H:%M'),
                    'Total Students': len(cum_df),
                    'Total Classes' : history_df['class_date'].nunique(),
                    'Avg Attendance': f"{cum_df['attendance_pct'].mean():.1f}%",
                    'Green Students': (cum_df['risk_level'] == 'Green').sum(),
                    'Yellow Students': (cum_df['risk_level'] == 'Yellow').sum(),
                    'Red Students'   : (cum_df['risk_level'] == 'Red').sum(),
                }
                pdf_bytes = generate_pdf(
                    cum_df, cumulative_df=cum_df,
                    class_name="Cumulative Report",
                    class_date=ts, summary=summary,
                )
                st.download_button(
                    "⬇️ Download PDF",
                    data=pdf_bytes,
                    file_name=f"cumulative_summary_{ts}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                )
            except Exception as e:
                st.button("⬇️ PDF (error)", disabled=True, help=str(e), use_container_width=True)

        # Risk breakdown table
        st.divider()
        st.subheader("Risk Level Breakdown")
        for risk, color_hex, emoji in [
            ('Green',  '#d5f5e3', '🟢'),
            ('Yellow', '#fef9e7', '🟡'),
            ('Red',    '#fadbd8', '🔴'),
        ]:
            grp = cum_df[cum_df['risk_level'] == risk]
            with st.expander(f"{emoji} {risk} — {len(grp)} students", expanded=(risk == 'Red')):
                if grp.empty:
                    st.write("No students in this category.")
                else:
                    st.dataframe(grp[['roll_number', 'name', 'attendance_pct', 'present_count', 'total_classes']],
                                 use_container_width=True, hide_index=True)

    # ── Single Class Report ────────────────────────────────────────────────
    elif report_type == "🗓️ Single Class Report":
        st.subheader("Single Class Report")

        class_options = classes_df.apply(
            lambda r: f"[{r['class_id']}] {r['class_date']} | {r['class_name']}", axis=1
        ).tolist()
        selected = st.selectbox("Select Class", ["— Select —"] + class_options)

        if selected != "— Select —":
            cid       = int(selected.split(']')[0].lstrip('['))
            class_row = classes_df[classes_df['class_id'] == cid].iloc[0]
            class_df  = load_attendance(class_id=cid)
            enrolled  = class_df[class_df['status'].isin(['Present', 'Absent'])]

            present  = (enrolled['status'] == 'Present').sum()
            absent   = (enrolled['status'] == 'Absent').sum()
            pct      = round(present / len(enrolled) * 100, 1) if len(enrolled) else 0

            st.dataframe(enrolled, use_container_width=True, hide_index=True)

            summary = {
                'Class Name'   : class_row['class_name'],
                'Date'         : class_row['class_date'],
                'Total Students': len(enrolled),
                'Present'      : present,
                'Absent'       : absent,
                'Attendance %' : f"{pct}%",
                'Threshold Used': f"{enrolled['min_duration_used'].iloc[0] if not enrolled.empty else '—'} minutes",
            }

            c1, c2, c3 = st.columns(3)
            with c1:
                st.download_button("⬇️ CSV",
                    data=generate_csv(enrolled),
                    file_name=f"class_{cid}_{ts}.csv",
                    mime="text/csv",
                    use_container_width=True)
            with c2:
                st.download_button("⬇️ Excel",
                    data=generate_excel(enrolled, title=f"Attendance – {class_row['class_name']}"),
                    file_name=f"class_{cid}_{ts}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True)
            with c3:
                try:
                    st.download_button("⬇️ PDF",
                        data=generate_pdf(enrolled,
                                          class_name=class_row['class_name'],
                                          class_date=class_row['class_date'],
                                          summary=summary),
                        file_name=f"class_{cid}_{ts}.pdf",
                        mime="application/pdf",
                        use_container_width=True)
                except Exception as e:
                    st.button("⬇️ PDF (error)", disabled=True, help=str(e), use_container_width=True)

    # ── Full History Export ────────────────────────────────────────────────
    elif report_type == "📚 Full History Export":
        st.subheader("Full Attendance History")
        st.dataframe(history_df, use_container_width=True, hide_index=True)

        c1, c2 = st.columns(2)
        with c1:
            st.download_button("⬇️ Full CSV",
                data=generate_csv(history_df),
                file_name=f"full_history_{ts}.csv",
                mime="text/csv",
                use_container_width=True)
        with c2:
            excel_bytes = generate_excel(
                history_df,
                cumulative_df=cum_df,
                history_df=history_df,
                title="Full Attendance History",
            )
            st.download_button("⬇️ Full Excel (Multi-sheet)",
                data=excel_bytes,
                file_name=f"full_history_{ts}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True)


if __name__ == "__main__":
    render()
