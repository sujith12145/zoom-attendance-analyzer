"""
app.py  –  Zoom Attendance Analyzer
=====================================
Main Streamlit application entry point.
Run with:  streamlit run app.py
"""

import streamlit as st
import sys, os

# ── Path setup ─────────────────────────────────────────────────────────────
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from config import APP_NAME, APP_VERSION, APP_ICON
from modules.database import get_attendance_summary, master_list_exists

# ── Page config (MUST be the first Streamlit call) ─────────────────────────
st.set_page_config(
    page_title=APP_NAME,
    page_icon=APP_ICON,
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "Get Help"    : "https://github.com/your-repo/zoom-attendance-analyzer",
        "Report a bug": "https://github.com/your-repo/zoom-attendance-analyzer/issues",
        "About"       : f"**{APP_NAME}** v{APP_VERSION}\n\nAI-powered attendance tracking for Zoom classes.",
    },
)

# ── Global CSS ──────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* ── Sidebar ─────────────────────────────────────────── */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #1a252f 0%, #2c3e50 100%);
}
[data-testid="stSidebar"] * { color: #ecf0f1 !important; }
[data-testid="stSidebar"] .stSelectbox label,
[data-testid="stSidebar"] .stSlider label,
[data-testid="stSidebar"] .stNumberInput label { color: #bdc3c7 !important; }

/* ── Metric cards ────────────────────────────────────── */
[data-testid="metric-container"] {
    background: #ffffff;
    border-radius: 12px;
    padding: 16px 20px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.08);
    border-left: 4px solid #3498db;
}
[data-testid="metric-container"] [data-testid="stMetricValue"] {
    font-size: 1.8rem !important;
    font-weight: 700;
    color: #2c3e50;
}

/* ── Header ──────────────────────────────────────────── */
header[data-testid="stHeader"] {
    background: linear-gradient(90deg, #2c3e50, #3498db);
}

/* ── Buttons ─────────────────────────────────────────── */
.stButton > button[kind="primary"] {
    background: linear-gradient(90deg, #3498db, #2980b9);
    border: none;
    border-radius: 8px;
    color: white;
    font-weight: 600;
    padding: 0.5rem 1.2rem;
    transition: transform 0.15s;
}
.stButton > button[kind="primary"]:hover { transform: translateY(-2px); }

/* ── Tabs ────────────────────────────────────────────── */
.stTabs [data-baseweb="tab"] {
    font-weight: 600;
    font-size: 0.92rem;
}
.stTabs [aria-selected="true"] {
    background: #ebf5fb !important;
    border-bottom: 3px solid #3498db !important;
}

/* ── DataFrames ──────────────────────────────────────── */
[data-testid="stDataFrame"] { border-radius: 8px; overflow: hidden; }

/* ── Page titles ─────────────────────────────────────── */
h1 { color: #2c3e50 !important; font-weight: 800 !important; }
h2 { color: #34495e !important; font-weight: 700 !important; }
h3 { color: #5d6d7e !important; }

/* ── Divider ─────────────────────────────────────────── */
hr { border-color: #eaecee !important; margin: 1.5rem 0 !important; }
</style>
""", unsafe_allow_html=True)

# ── Sidebar navigation ──────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(f"""
    <div style="text-align:center; padding: 1rem 0;">
        <div style="font-size:3rem;">🎓</div>
        <div style="font-size:1.1rem; font-weight:800; color:#ecf0f1; margin-top:4px;">
            {APP_NAME}
        </div>
        <div style="font-size:0.75rem; color:#95a5a6;">v{APP_VERSION}</div>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    # Quick stats
    try:
        summ = get_attendance_summary()
        col1, col2 = st.columns(2)
        col1.metric("Students", summ['total_students'])
        col2.metric("Classes",  summ['total_classes'])
        if summ['total_records']:
            st.progress(
                summ['avg_attendance_pct'] / 100,
                text=f"Avg Attendance: {summ['avg_attendance_pct']}%"
            )
    except Exception:
        pass

    st.divider()

    # Status badges
    if master_list_exists():
        st.success("✅ Master list loaded")
    else:
        st.warning("⚠️ No master list")

    st.divider()
    st.caption("Navigate using the **pages** above ↑")


# ── Home / Dashboard ────────────────────────────────────────────────────────
st.title(f"{APP_ICON} {APP_NAME}")
st.markdown(f"### AI-powered Zoom attendance tracking, analytics, and prediction &nbsp;&nbsp; `v{APP_VERSION}`",
            unsafe_allow_html=True)

st.divider()

# ── Quick-start cards ───────────────────────────────────────────────────────
st.subheader("🚀 Quick Start")
c1, c2, c3 = st.columns(3)

with c1:
    st.markdown("""
    <div style="background:#ebf5fb; border-radius:12px; padding:1.2rem; border-left:4px solid #3498db;">
        <h4 style="margin:0; color:#2c3e50;">Step 1 — Upload Roster</h4>
        <p style="color:#5d6d7e; font-size:0.88rem; margin-top:8px;">
        Upload your master student list (CSV/Excel) with roll numbers and names.
        The system cleans and stores it permanently.
        </p>
        <code style="font-size:0.8rem;">📋 Master List page</code>
    </div>""", unsafe_allow_html=True)

with c2:
    st.markdown("""
    <div style="background:#eafaf1; border-radius:12px; padding:1.2rem; border-left:4px solid #2ecc71;">
        <h4 style="margin:0; color:#2c3e50;">Step 2 — Upload Zoom CSV</h4>
        <p style="color:#5d6d7e; font-size:0.88rem; margin-top:8px;">
        After each class, export the participant report from Zoom and upload it here.
        Attendance is auto-calculated with fuzzy name matching.
        </p>
        <code style="font-size:0.8rem;">📤 Upload Zoom Attendance page</code>
    </div>""", unsafe_allow_html=True)

with c3:
    st.markdown("""
    <div style="background:#fef9e7; border-radius:12px; padding:1.2rem; border-left:4px solid #f39c12;">
        <h4 style="margin:0; color:#2c3e50;">Step 3 — Analyse & Export</h4>
        <p style="color:#5d6d7e; font-size:0.88rem; margin-top:8px;">
        View dashboards, ML risk predictions, trend forecasts, and download
        formatted reports in CSV, Excel, or PDF.
        </p>
        <code style="font-size:0.8rem;">📈 Analytics + 🤖 ML pages</code>
    </div>""", unsafe_allow_html=True)

st.divider()

# ── Features grid ──────────────────────────────────────────────────────────
st.subheader("✨ Key Features")
f1, f2, f3, f4 = st.columns(4)

features = [
    ("🔍", "Smart Matching",
     "Roll-number priority, RapidFuzz token-sort, and Levenshtein distance for robust name matching."),
    ("⏱️", "Multi-session Merge",
     "Automatically merges multiple join/leave events per student and sums durations."),
    ("📊", "Rich Analytics",
     "Pie, bar, histogram, heatmap, gauge, and monthly trend charts with interactive filters."),
    ("🤖", "ML Predictions",
     "Random Forest risk classification, Gradient Boosting forecasting, Isolation Forest anomaly detection."),
]
for col, (icon, title, desc) in zip([f1, f2, f3, f4], features):
    col.markdown(f"""
    <div style="background:#f8f9fa; border-radius:10px; padding:1rem; text-align:center; height:160px;">
        <div style="font-size:2rem;">{icon}</div>
        <div style="font-weight:700; color:#2c3e50; margin:6px 0 4px;">{title}</div>
        <div style="font-size:0.82rem; color:#7f8c8d;">{desc}</div>
    </div>""", unsafe_allow_html=True)

st.divider()

# ── Tech stack ─────────────────────────────────────────────────────────────
st.subheader("🛠️ Technology Stack")
tech = st.columns(6)
stack = [
    ("🐍", "Python 3.11+"),
    ("🌊", "Streamlit"),
    ("🐼", "Pandas / NumPy"),
    ("🤖", "Scikit-Learn"),
    ("🔍", "RapidFuzz"),
    ("📊", "Plotly"),
]
for col, (icon, name) in zip(tech, stack):
    col.markdown(
        f"<div style='text-align:center; padding:8px; background:#f0f4f8; border-radius:8px;'>"
        f"<div style='font-size:1.5rem;'>{icon}</div>"
        f"<div style='font-size:0.8rem; font-weight:600; color:#2c3e50;'>{name}</div></div>",
        unsafe_allow_html=True,
    )
