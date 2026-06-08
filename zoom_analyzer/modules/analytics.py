"""
Module: analytics.py
=====================
Build all Plotly figures & summary tables used in the dashboard:
  • Pie: present vs absent
  • Bar: per-class attendance count
  • Distribution: attendance % histogram
  • Trend: monthly attendance line
  • Top / Low performers tables
  • Risk breakdown
"""

import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    COLOR_GREEN, COLOR_YELLOW, COLOR_RED, COLOR_BLUE, COLOR_DARK, COLOR_LIGHT
)

# ─── Common layout defaults ──────────────────────────────────────────────────
_LAYOUT = dict(
    paper_bgcolor='rgba(0,0,0,0)',
    plot_bgcolor ='rgba(0,0,0,0)',
    font=dict(family='Inter, sans-serif', color='#2c3e50'),
    margin=dict(l=40, r=40, t=50, b=40),
)


# ─────────────────────────────────────────────────────────────────────────────
# 1. Pie – Present vs Absent (single class)
# ─────────────────────────────────────────────────────────────────────────────

def fig_pie_present_absent(attendance_df: pd.DataFrame) -> go.Figure:
    counts = (
        attendance_df[attendance_df['status'].isin(['Present', 'Absent'])]
        ['status'].value_counts().reset_index()
    )
    counts.columns = ['Status', 'Count']
    fig = px.pie(
        counts, names='Status', values='Count',
        color='Status',
        color_discrete_map={'Present': COLOR_GREEN, 'Absent': COLOR_RED},
        hole=0.45,
        title='Present vs Absent',
    )
    fig.update_layout(**_LAYOUT)
    fig.update_traces(textposition='inside', textinfo='percent+label')
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# 2. Bar – per-class attendance count
# ─────────────────────────────────────────────────────────────────────────────

def fig_bar_per_class(history_df: pd.DataFrame) -> go.Figure:
    df = history_df[history_df['status'].isin(['Present', 'Absent'])].copy()
    grp = df.groupby(['class_date', 'class_name', 'status']).size().reset_index(name='count')
    grp['label'] = grp['class_date'] + '\n' + grp['class_name']

    fig = px.bar(
        grp, x='label', y='count', color='status',
        barmode='group',
        color_discrete_map={'Present': COLOR_GREEN, 'Absent': COLOR_RED},
        title='Attendance per Class',
        labels={'label': 'Class', 'count': 'Students'},
    )
    fig.update_layout(**_LAYOUT, xaxis_tickangle=-30)
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# 3. Histogram – attendance % distribution
# ─────────────────────────────────────────────────────────────────────────────

def fig_histogram_attendance_pct(cumulative_df: pd.DataFrame) -> go.Figure:
    fig = px.histogram(
        cumulative_df, x='attendance_pct', nbins=20,
        title='Attendance % Distribution',
        labels={'attendance_pct': 'Attendance %'},
        color_discrete_sequence=[COLOR_BLUE],
    )
    fig.update_layout(**_LAYOUT)
    fig.add_vline(x=75, line_dash='dash', line_color=COLOR_GREEN,
                  annotation_text='75% threshold')
    fig.add_vline(x=50, line_dash='dash', line_color=COLOR_YELLOW,
                  annotation_text='50% threshold')
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# 4. Line – monthly attendance trend
# ─────────────────────────────────────────────────────────────────────────────

def fig_line_monthly_trend(history_df: pd.DataFrame) -> go.Figure:
    df = history_df[history_df['status'].isin(['Present', 'Absent'])].copy()
    df['month'] = pd.to_datetime(df['class_date'], errors='coerce').dt.to_period('M').astype(str)
    monthly = df.groupby('month').agg(
        total   =('status', 'count'),
        present =('status', lambda x: (x == 'Present').sum()),
    ).reset_index()
    monthly['pct'] = (monthly['present'] / monthly['total'] * 100).round(1)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=monthly['month'], y=monthly['pct'],
        mode='lines+markers',
        line=dict(color=COLOR_BLUE, width=3),
        marker=dict(size=8),
        name='Avg Attendance %',
        fill='tozeroy',
        fillcolor='rgba(52,152,219,0.15)',
    ))
    fig.update_layout(
        **_LAYOUT,
        title='Monthly Attendance Trend',
        xaxis_title='Month',
        yaxis_title='Attendance %',
        yaxis_range=[0, 105],
    )
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# 5. Bar – top N students
# ─────────────────────────────────────────────────────────────────────────────

def fig_top_students(cumulative_df: pd.DataFrame, n: int = 10) -> go.Figure:
    top = cumulative_df.nlargest(n, 'attendance_pct')
    fig = px.bar(
        top, x='attendance_pct', y='name',
        orientation='h',
        color='attendance_pct',
        color_continuous_scale=[[0, COLOR_YELLOW], [1, COLOR_GREEN]],
        title=f'Top {n} Students by Attendance',
        labels={'attendance_pct': 'Attendance %', 'name': ''},
        text='attendance_pct',
    )
    fig.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
    fig.update_layout(**_LAYOUT, coloraxis_showscale=False, yaxis_autorange='reversed')
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# 6. Bar – low-attendance students
# ─────────────────────────────────────────────────────────────────────────────

def fig_low_students(cumulative_df: pd.DataFrame, threshold: float = 75.0, n: int = 10) -> go.Figure:
    low = cumulative_df[cumulative_df['attendance_pct'] < threshold].nsmallest(n, 'attendance_pct')
    if low.empty:
        fig = go.Figure()
        fig.add_annotation(text='🎉 All students meet the threshold!',
                           xref='paper', yref='paper', x=0.5, y=0.5,
                           showarrow=False, font=dict(size=16))
        fig.update_layout(**_LAYOUT, title='Low-Attendance Students')
        return fig

    fig = px.bar(
        low, x='attendance_pct', y='name',
        orientation='h',
        color='attendance_pct',
        color_continuous_scale=[[0, COLOR_RED], [1, COLOR_YELLOW]],
        title=f'Students Below {threshold}% Attendance',
        labels={'attendance_pct': 'Attendance %', 'name': ''},
        text='attendance_pct',
    )
    fig.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
    fig.update_layout(**_LAYOUT, coloraxis_showscale=False, yaxis_autorange='reversed')
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# 7. Stacked bar – risk breakdown
# ─────────────────────────────────────────────────────────────────────────────

def fig_risk_breakdown(cumulative_df: pd.DataFrame) -> go.Figure:
    counts = cumulative_df['risk_level'].value_counts().reindex(
        ['Green', 'Yellow', 'Red'], fill_value=0
    ).reset_index()
    counts.columns = ['Risk', 'Count']

    color_map = {'Green': COLOR_GREEN, 'Yellow': COLOR_YELLOW, 'Red': COLOR_RED}
    fig = px.bar(
        counts, x='Risk', y='Count',
        color='Risk',
        color_discrete_map=color_map,
        title='Student Risk Distribution',
        text='Count',
    )
    fig.update_traces(textposition='outside')
    fig.update_layout(**_LAYOUT, showlegend=False)
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# 8. Heatmap – student × class attendance
# ─────────────────────────────────────────────────────────────────────────────

def fig_attendance_heatmap(history_df: pd.DataFrame, max_students: int = 40) -> go.Figure:
    df = history_df[history_df['status'].isin(['Present', 'Absent'])].copy()
    df['status_num'] = (df['status'] == 'Present').astype(int)
    df['class_label'] = df['class_date'] + ' ' + df['class_name']

    pivot = df.pivot_table(
        index='name', columns='class_label', values='status_num', aggfunc='max'
    ).fillna(0)

    if len(pivot) > max_students:
        pivot = pivot.head(max_students)

    fig = go.Figure(data=go.Heatmap(
        z=pivot.values,
        x=pivot.columns.tolist(),
        y=pivot.index.tolist(),
        colorscale=[[0, COLOR_RED], [1, COLOR_GREEN]],
        showscale=False,
        hovertemplate='Student: %{y}<br>Class: %{x}<br>%{customdata}<extra></extra>',
        customdata=[['Present' if v == 1 else 'Absent' for v in row] for row in pivot.values],
    ))
    fig.update_layout(
        **_LAYOUT,
        title='Attendance Heatmap (Student × Class)',
        xaxis_tickangle=-40,
        height=max(400, len(pivot) * 18 + 100),
    )
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# 9. Gauge – overall attendance %
# ─────────────────────────────────────────────────────────────────────────────

def fig_gauge_overall(avg_pct: float) -> go.Figure:
    color = COLOR_GREEN if avg_pct >= 75 else (COLOR_YELLOW if avg_pct >= 50 else COLOR_RED)
    fig = go.Figure(go.Indicator(
        mode='gauge+number',
        value=avg_pct,
        number={'suffix': '%'},
        gauge={
            'axis': {'range': [0, 100]},
            'bar': {'color': color},
            'steps': [
                {'range': [0, 50],  'color': 'rgba(231,76,60,0.2)'},
                {'range': [50, 75], 'color': 'rgba(243,156,18,0.2)'},
                {'range': [75, 100],'color': 'rgba(46,204,113,0.2)'},
            ],
            'threshold': {'line': {'color': COLOR_DARK, 'width': 4}, 'value': 75},
        },
        title={'text': 'Overall Attendance'},
    ))
    fig.update_layout(**_LAYOUT, height=280)
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# 10. Combined dashboard figure (2×2 subplots)
# ─────────────────────────────────────────────────────────────────────────────

def fig_dashboard_overview(
    history_df: pd.DataFrame,
    cumulative_df: pd.DataFrame,
) -> go.Figure:
    """Composite 2×2 figure for a quick overview."""
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=(
            'Attendance per Class',
            'Attendance % Distribution',
            'Monthly Trend',
            'Risk Distribution',
        ),
        specs=[[{'type': 'bar'}, {'type': 'histogram'}],
               [{'type': 'scatter'}, {'type': 'bar'}]],
    )

    # ── Per-class ──────────────────────────────────────────────────────────
    df = history_df[history_df['status'].isin(['Present', 'Absent'])].copy()
    grp = df.groupby(['class_date', 'status']).size().reset_index(name='count')
    for status, color in [('Present', COLOR_GREEN), ('Absent', COLOR_RED)]:
        sub = grp[grp['status'] == status]
        fig.add_trace(go.Bar(x=sub['class_date'], y=sub['count'],
                             name=status, marker_color=color,
                             legendgroup=status), row=1, col=1)

    # ── Histogram ─────────────────────────────────────────────────────────
    fig.add_trace(go.Histogram(
        x=cumulative_df['attendance_pct'], nbinsx=15,
        marker_color=COLOR_BLUE, name='Distribution',
    ), row=1, col=2)

    # ── Monthly trend ─────────────────────────────────────────────────────
    df['month'] = pd.to_datetime(df['class_date'], errors='coerce').dt.to_period('M').astype(str)
    monthly = df.groupby('month').agg(
        total=('status', 'count'),
        present=('status', lambda x: (x == 'Present').sum()),
    ).reset_index()
    monthly['pct'] = (monthly['present'] / monthly['total'] * 100).round(1)
    fig.add_trace(go.Scatter(
        x=monthly['month'], y=monthly['pct'],
        mode='lines+markers',
        line=dict(color=COLOR_BLUE, width=2),
        name='Monthly %',
    ), row=2, col=1)

    # ── Risk ──────────────────────────────────────────────────────────────
    risk_counts = cumulative_df['risk_level'].value_counts().reindex(
        ['Green', 'Yellow', 'Red'], fill_value=0
    )
    fig.add_trace(go.Bar(
        x=risk_counts.index, y=risk_counts.values,
        marker_color=[COLOR_GREEN, COLOR_YELLOW, COLOR_RED],
        name='Risk',
    ), row=2, col=2)

    fig.update_layout(
        **_LAYOUT,
        height=600,
        showlegend=False,
        title_text='Attendance Dashboard Overview',
    )
    return fig
