import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from ui.ui_charts import (
    render_pulse_cards,
    render_flow_trends,
    render_status_funnel,
    render_project_gravity,
    render_oldest_orders_table,
    render_analysis_distribution,
)
from translation import t
from logic import calculate_workload_index


@st.fragment(run_every="60s")
def render_dashboard_fragment(all_orders, df):
    """
    Isoliertes Dashboard-Fragment für Auto-Refresh.
    Berechnet echte Metriken aus der Datenbank.
    """
    if df.empty:
        st.info(t("no_order_state_dashboard"))
        return



    active_df = df[
        ~df["status"].isin(["cat_order_released", "cat_order_annulated"])
    ].copy()


    open_orders_count = len(active_df)


    completed = df[df["status"] == "cat_order_released"].copy()
    if not completed.empty:
        completed["tat"] = (
            completed["completed_at"] - completed["created_at"]
        ).dt.total_seconds() / 86400
        avg_tat = f"{completed['tat'].mean():.1f}"
    else:
        avg_tat = "--"


    total_points, load_index = calculate_workload_index(active_df, weekly_capacity=100)
    status_msg = (
        f"🔴 {t('workload_overloaded')}"
        if load_index > 120
        else f"🟢 {t('workload_ok')}"
    )

    all_meth_flat = []

    for s_list in active_df["samples"]:
        for s in s_list:
            if s["methods"]:
                all_meth_flat.extend(
                    [m.strip() for m in s["methods"].split(",") if m.strip()]
                )

    total_analyses = len(all_meth_flat)


    render_pulse_cards(open_orders_count, avg_tat, total_points, load_index, status_msg)
    st.divider()
    render_analysis_distribution(all_orders, df["id"].tolist())
    st.divider()

    col_left, col_right = st.columns(2)
    with col_left:
        render_flow_trends(df)
        st.write("")
        render_project_gravity(df)
    with col_right:
        render_status_funnel(df)
        st.write("")
        render_oldest_orders_table(df)
