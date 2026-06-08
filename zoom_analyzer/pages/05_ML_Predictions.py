"""
Page: 05_ML_Predictions.py
============================
Machine-learning powered attendance predictions and risk analysis.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.database              import load_full_history
from modules.ml_predictor          import run_full_ml_pipeline
from config import COLOR_GREEN, COLOR_YELLOW, COLOR_RED


def render():
    from modules.auth import check_authentication
    if not check_authentication():
        st.stop()

    st.title("🤖 ML Predictions & Risk Analysis")
    st.markdown("Uses **Random Forest**, **Gradient Boosting**, and **Isolation Forest** to predict "
                "attendance trends and identify at-risk students.")

    history_df = load_full_history()
    if history_df.empty:
        st.info("📭 No data yet. Upload attendance records first.")
        return

    n_classes   = history_df['class_date'].nunique()
    n_students  = history_df['roll_number'].nunique()

    if n_classes < 3:
        st.warning(f"⚠️ ML requires at least **3 classes** of history. Currently: {n_classes} class(es).")
        st.info("Upload more Zoom CSVs and come back here!")
        return

    # ── Run pipeline ───────────────────────────────────────────────────────
    with st.spinner("🧠 Training ML models… (may take a few seconds)"):
        try:
            results = run_full_ml_pipeline(history_df)
        except Exception as e:
            st.error(f"ML error: {e}")
            import traceback; st.code(traceback.format_exc())
            return

    # ── KPI ────────────────────────────────────────────────────────────────
    train_metrics = results.get('train_metrics', {})
    trend_metrics = results.get('trend_train_metrics', {})
    risk_pred     = results.get('risk_predictions', pd.DataFrame())
    forecast      = results.get('forecast', [])
    anomalies     = results.get('anomalies', pd.DataFrame())

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Training Samples",  train_metrics.get('n_samples', '—'))
    k2.metric("CV Accuracy",       f"{train_metrics.get('cv_accuracy', 0):.1f}%")
    k3.metric("Trend MAE",         f"±{trend_metrics.get('mae', '—')}%")
    k4.metric("Anomalies Detected",len(anomalies))

    st.divider()

    # ── Tabs ───────────────────────────────────────────────────────────────
    tab_risk, tab_forecast, tab_anomaly, tab_importance = st.tabs([
        "🎯 Risk Predictions",
        "📈 Attendance Forecast",
        "⚠️ Anomaly Detection",
        "🔍 Feature Importance",
    ])

    # ── Risk Predictions ───────────────────────────────────────────────────
    with tab_risk:
        if risk_pred.empty:
            st.info("Not enough data for risk predictions.")
        else:
            st.subheader("Student Risk Classification")
            st.markdown(f"Model: **Random Forest Classifier** | Accuracy: **{train_metrics.get('cv_accuracy', '—')}%**")

            # Filter
            risk_filter = st.selectbox("Filter by predicted risk", ['All', 'Green', 'Yellow', 'Red'])
            show = risk_pred if risk_filter == 'All' else risk_pred[risk_pred['predicted_risk'] == risk_filter]

            # Colour badge column
            show = show.copy()
            if 'predicted_risk' in show.columns:
                show['Risk Level'] = show['predicted_risk'].apply(_risk_badge)

            disp_cols = ['roll_number', 'name', 'attendance_pct', 'last_n_present',
                         'streak_present', 'streak_absent', 'avg_duration',
                         'predicted_risk', 'confidence']
            disp_cols = [c for c in disp_cols if c in show.columns]
            st.dataframe(
                show[disp_cols].style.apply(_risk_row_style, axis=1),
                use_container_width=True, height=430,
            )

            # Risk pie
            risk_counts = risk_pred['predicted_risk'].value_counts().reset_index()
            risk_counts.columns = ['Risk', 'Count']
            fig = px.pie(risk_counts, names='Risk', values='Count',
                         color='Risk',
                         color_discrete_map={'Green': COLOR_GREEN, 'Yellow': COLOR_YELLOW, 'Red': COLOR_RED},
                         title='Predicted Risk Distribution',
                         hole=0.4)
            st.plotly_chart(fig, use_container_width=True)

    # ── Forecast ───────────────────────────────────────────────────────────
    with tab_forecast:
        st.subheader("📊 Attendance Trend Forecast")
        st.markdown("**Gradient Boosting Regressor** predicts class-level attendance % for upcoming sessions.")

        if not forecast:
            st.warning("Not enough class history to forecast (need ≥5 classes).")
        else:
            # Historical trend
            df = history_df[history_df['status'].isin(['Present', 'Absent'])].copy()
            class_stats = df.groupby('class_date').agg(
                total   =('status', 'count'),
                present =('status', lambda x: (x == 'Present').sum()),
            ).reset_index()
            class_stats['pct']   = (class_stats['present'] / class_stats['total'] * 100).round(1)
            class_stats['label'] = class_stats['class_date']
            class_stats['type']  = 'Historical'

            # Forecast points
            last_class_num = len(class_stats)
            forecast_rows = []
            for f in forecast:
                forecast_rows.append({
                    'label': f"Class {f['class_number']} (predicted)",
                    'pct':   f['predicted_pct'],
                    'type':  'Forecast',
                })
            forecast_df = pd.DataFrame(forecast_rows)

            # Combine for chart
            hist_chart = class_stats[['label', 'pct', 'type']].rename(columns={'pct': 'Attendance %'})
            fore_chart = forecast_df.rename(columns={'pct': 'Attendance %'})
            combined   = pd.concat([hist_chart, fore_chart], ignore_index=True)

            fig = go.Figure()
            hist_part = combined[combined['type'] == 'Historical']
            fore_part = combined[combined['type'] == 'Forecast']

            fig.add_trace(go.Scatter(
                x=hist_part['label'], y=hist_part['Attendance %'],
                mode='lines+markers',
                name='Historical',
                line=dict(color='#3498db', width=3),
                marker=dict(size=8),
            ))
            fig.add_trace(go.Scatter(
                x=fore_part['label'], y=fore_part['Attendance %'],
                mode='lines+markers',
                name='Forecast',
                line=dict(color='#e67e22', width=3, dash='dash'),
                marker=dict(size=10, symbol='star'),
            ))
            fig.update_layout(
                title='Attendance Trend & Forecast',
                xaxis_title='Class',
                yaxis_title='Attendance %',
                yaxis_range=[0, 105],
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
            )
            st.plotly_chart(fig, use_container_width=True)

            # Forecast table
            st.subheader("Predicted Values")
            for f in forecast:
                col = "#2ecc71" if f['predicted_pct'] >= 75 else ("#f39c12" if f['predicted_pct'] >= 50 else "#e74c3c")
                st.markdown(
                    f"**Class {f['class_number']}** → "
                    f"<span style='background:{col};color:white;padding:2px 10px;border-radius:10px;'>"
                    f"{f['predicted_pct']:.1f}%</span>",
                    unsafe_allow_html=True,
                )

    # ── Anomaly Detection ─────────────────────────────────────────────────
    with tab_anomaly:
        st.subheader("⚠️ Sudden Attendance Drop Detection")
        st.markdown("**Isolation Forest** identifies students whose recent attendance "
                    "deviates significantly from their own baseline.")

        if anomalies.empty:
            st.success("🎉 No anomalous attendance patterns detected!")
        else:
            st.error(f"🚨 {len(anomalies)} student(s) show sudden attendance drops!")
            st.dataframe(anomalies, use_container_width=True, hide_index=True)
            st.markdown("""
**Recommended actions:**
- 📧 Send a personal email / notification
- 📞 Contact the student or guardian
- 🔍 Investigate technical issues (connectivity, device problems)
            """)

    # ── Feature Importance ────────────────────────────────────────────────
    with tab_importance:
        st.subheader("🔍 Feature Importance (Random Forest)")
        fi = train_metrics.get('feature_importances', {})
        if fi:
            fi_df = pd.DataFrame(list(fi.items()), columns=['Feature', 'Importance'])
            fi_df = fi_df.sort_values('Importance', ascending=True)
            fig = px.bar(fi_df, x='Importance', y='Feature', orientation='h',
                         color='Importance',
                         color_continuous_scale='blues',
                         title='Feature Importances')
            fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig, use_container_width=True)
            st.markdown("""
| Feature | Meaning |
|---------|---------|
| `attendance_pct` | Overall historical attendance % |
| `last_n_present` | Average presence in last N classes |
| `last_n_trend` | Trend direction (improving/declining) |
| `streak_present` | Current consecutive present streak |
| `streak_absent` | Current consecutive absent streak |
| `avg_duration` | Average time spent in class |
| `std_duration` | Variability in time spent |
| `most_common_dow` | Most frequent class day of week |
            """)
        else:
            st.info("Feature importances will appear after model training completes.")


def _risk_badge(risk: str) -> str:
    emoji = {'Green': '🟢', 'Yellow': '🟡', 'Red': '🔴'}.get(risk, '⚪')
    return f"{emoji} {risk}"


def _risk_row_style(row):
    risk_col = 'predicted_risk' if 'predicted_risk' in row.index else 'risk_label'
    if risk_col in row.index:
        v = row[risk_col]
        if v == 'Green':  return ['background-color:#d5f5e3'] * len(row)
        if v == 'Yellow': return ['background-color:#fef9e7'] * len(row)
        if v == 'Red':    return ['background-color:#fadbd8'] * len(row)
    return [''] * len(row)


if __name__ == "__main__":
    render()
