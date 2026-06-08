"""
Page: 04_Analytics.py
=======================
Interactive analytics dashboard with Plotly charts.
"""

import streamlit as st
import pandas as pd
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.database                import load_full_history, get_attendance_summary
from modules.attendance_calculator   import compute_cumulative_stats, apply_risk_labels
from modules.analytics import (
    fig_pie_present_absent,
    fig_bar_per_class,
    fig_histogram_attendance_pct,
    fig_line_monthly_trend,
    fig_top_students,
    fig_low_students,
    fig_risk_breakdown,
    fig_attendance_heatmap,
    fig_gauge_overall,
    fig_dashboard_overview,
)
from config import DEFAULT_GREEN_THRESHOLD, DEFAULT_YELLOW_THRESHOLD


def render():
    st.title("📈 Analytics Dashboard")

    history_df = load_full_history()
    if history_df.empty:
        st.info("📭 No data yet. Upload attendance records first.")
        return

    # ── Sidebar filters ────────────────────────────────────────────────────
    with st.sidebar:
        st.header("🔧 Dashboard Filters")
        green_th  = st.slider("Green threshold (%)", 60, 95, DEFAULT_GREEN_THRESHOLD, 5)
        yellow_th = st.slider("Yellow threshold (%)", 30, 70, DEFAULT_YELLOW_THRESHOLD, 5)
        top_n     = st.slider("Top/Low students to show", 5, 20, 10)
        st.divider()
        st.markdown("**Filter by class date range**")
        all_dates = sorted(history_df['class_date'].unique().tolist())
        if len(all_dates) >= 2:
            date_range = st.select_slider(
                "Date range",
                options=all_dates,
                value=(all_dates[0], all_dates[-1]),
            )
            history_df = history_df[
                (history_df['class_date'] >= date_range[0]) &
                (history_df['class_date'] <= date_range[1])
            ]

    # ── Compute ────────────────────────────────────────────────────────────
    cum_df = compute_cumulative_stats(history_df)
    cum_df = apply_risk_labels(cum_df, green_th, yellow_th)

    summ   = get_attendance_summary()
    avg_pct = cum_df['attendance_pct'].mean() if not cum_df.empty else 0.0

    # ── KPI row ────────────────────────────────────────────────────────────
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("👥 Total Students",    summ['total_students'])
    k2.metric("📅 Total Classes",     summ['total_classes'])
    k3.metric("✅ Avg Present",        f"{summ['avg_attendance_pct']}%")
    k4.metric("🟢 Green",             (cum_df['risk_level'] == 'Green').sum()  if not cum_df.empty else 0)
    k5.metric("🔴 Red (At Risk)",     (cum_df['risk_level'] == 'Red').sum()    if not cum_df.empty else 0)

    st.divider()

    # ── Gauge + Pie ────────────────────────────────────────────────────────
    col_g, col_p = st.columns([1, 2])
    with col_g:
        st.plotly_chart(fig_gauge_overall(avg_pct), use_container_width=True)
    with col_p:
        enrolled = history_df[history_df['status'].isin(['Present', 'Absent'])]
        if not enrolled.empty:
            st.plotly_chart(fig_pie_present_absent(enrolled), use_container_width=True)

    # ── Per-class bar ──────────────────────────────────────────────────────
    st.plotly_chart(fig_bar_per_class(history_df), use_container_width=True)

    # ── Monthly trend ──────────────────────────────────────────────────────
    st.plotly_chart(fig_line_monthly_trend(history_df), use_container_width=True)

    # ── Distribution ──────────────────────────────────────────────────────
    st.plotly_chart(fig_histogram_attendance_pct(cum_df), use_container_width=True)

    # ── Top + Low ──────────────────────────────────────────────────────────
    col_top, col_low = st.columns(2)
    with col_top:
        st.plotly_chart(fig_top_students(cum_df, top_n), use_container_width=True)
    with col_low:
        st.plotly_chart(fig_low_students(cum_df, green_th, top_n), use_container_width=True)

    # ── Risk breakdown ─────────────────────────────────────────────────────
    col_risk, col_heat = st.columns([1, 2])
    with col_risk:
        st.plotly_chart(fig_risk_breakdown(cum_df), use_container_width=True)
    with col_heat:
        if len(history_df['name'].unique()) <= 60:
            st.plotly_chart(fig_attendance_heatmap(history_df), use_container_width=True)
        else:
            st.info("Heatmap limited to ≤60 students. Use filters to narrow down.")

    # ── Risk tables ────────────────────────────────────────────────────────
    st.divider()
    st.subheader("🎯 Students by Risk Level")
    tab_green, tab_yellow, tab_red = st.tabs(["🟢 Green", "🟡 Yellow", "🔴 Red"])

    with tab_green:
        g = cum_df[cum_df['risk_level'] == 'Green']
        st.success(f"{len(g)} students are performing well (≥{green_th}% attendance)")
        if not g.empty: st.dataframe(g, use_container_width=True, hide_index=True)

    with tab_yellow:
        y = cum_df[cum_df['risk_level'] == 'Yellow']
        st.warning(f"{len(y)} students need attention ({yellow_th}%–{green_th}% attendance)")
        if not y.empty: st.dataframe(y, use_container_width=True, hide_index=True)

    with tab_red:
        r = cum_df[cum_df['risk_level'] == 'Red']
        st.error(f"{len(r)} students are at critical risk (<{yellow_th}% attendance)")
        if not r.empty: st.dataframe(r, use_container_width=True, hide_index=True)


if __name__ == "__main__":
    render()
