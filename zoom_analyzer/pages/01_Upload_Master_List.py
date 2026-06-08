"""
Page: 01_Upload_Master_List.py
================================
Streamlit page for uploading and managing the master student roster.
"""

import streamlit as st
import pandas as pd
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.preprocessor import load_master_list
from modules.database     import save_master_list, load_master_list_db, master_list_exists


def render():
    st.title("📋 Master Student List")
    st.markdown("Upload your student roster once. It will be stored permanently and used for all future attendance sessions.")

    # ── Current state ─────────────────────────────────────────────────────
    if master_list_exists():
        existing = load_master_list_db()
        st.success(f"✅ Master list loaded — **{len(existing)} students** registered")
        with st.expander("👀 View current student list", expanded=False):
            st.dataframe(existing, use_container_width=True, height=300)
        st.info("ℹ️ Upload a new file to **replace** the current list.")
        st.divider()

    # ── Upload widget ─────────────────────────────────────────────────────
    st.subheader("Upload Student Roster")
    col1, col2 = st.columns([2, 1])

    with col1:
        uploaded = st.file_uploader(
            "Choose CSV or Excel file",
            type=['csv', 'xlsx', 'xls'],
            help="Required columns: Roll Number, Name",
        )

    with col2:
        st.markdown("**Required columns:**")
        st.markdown("- `Roll Number` (or `Roll No`, `ID`)")
        st.markdown("- `Name` (or `Student Name`)")
        st.download_button(
            "📥 Download Sample Template",
            data=_sample_template_csv(),
            file_name="master_list_template.csv",
            mime="text/csv",
        )

    if uploaded:
        try:
            with st.spinner("Processing…"):
                df, warnings = load_master_list(uploaded)

            for w in warnings:
                st.warning(w)

            # Preview
            st.subheader("Preview (first 10 rows)")
            st.dataframe(df.head(10), use_container_width=True)
            st.info(f"📊 Total valid students detected: **{len(df)}**")

            col_a, col_b = st.columns(2)
            with col_a:
                if st.button("💾 Save to Database", type="primary", use_container_width=True):
                    n = save_master_list(df)
                    st.success(f"✅ Saved **{n} students** to database!")
                    st.balloons()
                    st.rerun()
            with col_b:
                if st.button("❌ Cancel", use_container_width=True):
                    st.rerun()

        except ValueError as e:
            st.error(f"❌ {e}")
        except Exception as e:
            st.error(f"❌ Unexpected error: {e}")

    # ── Format guide ──────────────────────────────────────────────────────
    with st.expander("📖 File Format Guide"):
        st.markdown("""
**CSV / Excel format:**

| Roll Number | Name         |
|-------------|--------------|
| CS-21-001   | John Smith   |
| CS-21-002   | Jane Doe     |

**Accepted column name variants:**
- Roll Number: `roll number`, `roll no`, `rollno`, `enrollment`, `id`, `student id`
- Name: `name`, `student name`, `full name`

**Cleaning applied automatically:**
- Extra spaces removed
- Capitalisation normalised
- Special characters cleaned
- Duplicate roll numbers removed
        """)


def _sample_template_csv() -> bytes:
    sample = pd.DataFrame([
        {"Roll Number": "CS-21-001", "Name": "Aarav Kumar"},
        {"Roll Number": "CS-21-002", "Name": "Priya Sharma"},
        {"Roll Number": "CS-21-003", "Name": "Rahul Singh"},
    ])
    return sample.to_csv(index=False).encode()


if __name__ == "__main__":
    render()
