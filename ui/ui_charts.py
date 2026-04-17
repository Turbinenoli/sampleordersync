import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
from translation import t
import logic




COLORS = {
    "primary": "#CFA071",  # Muted Ochre
    "secondary": "#89A6B3",  # Deep Steel
    "accent": "#E2B05E",  # Ocker
    "success": "#9EB384",  # Salbei
    "danger": "#D67B72",  # Terrakotta
    "text": "#E8E3DF",
    "grid": "rgba(255,255,255,0.05)",
    "bg_card": "rgba(255,255,255,0.02)",
}

CHART_LAYOUT_BASE = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color=COLORS["text"], family="Inter, sans-serif"),
    margin=dict(l=20, r=20, t=40, b=20),
    xaxis=dict(
        showgrid=True, gridcolor=COLORS["grid"], zeroline=False, tickfont=dict(size=11)
    ),
    yaxis=dict(
        showgrid=True, gridcolor=COLORS["grid"], zeroline=False, tickfont=dict(size=11)
    ),
    hoverlabel=dict(bgcolor="#24211E", font_size=13, font_family="Inter"),
)


def render_pulse_cards(total_samples, avg_tat, total_points, load_index, status_msg):
    """Obere Kacheln für den schnellen Überblick."""
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric(t("total_orders"), f"{total_samples:,}")
    c2.metric(t("stat_tat"), f"{avg_tat} d")
    c3.metric(t("stat_volume"), f"{total_points:,}")
    c4.metric(t("stat_index"), f"{load_index}")
    c5.metric(t("stat_indicator"), f"{status_msg}")


def render_analysis_distribution(all_orders, filtered_ids):
    """
    PRIORITÄT 1: Top 5 als Donut oder Alle Analysen als Bar-Chart.
    """
    st.markdown(f"#### 🧪 {t('analysis_dist')}")

    meths = {}
    for o in all_orders:
        if o["id"] in filtered_ids and o["status"] not in [
            "cat_order_annulated",
            "cat_order_released",
        ]:
            for s in o["samples"]:
                if s["methods"]:
                    for m in [x.strip() for x in s["methods"].split(",") if x.strip()]:
                        meths[m] = meths.get(m, 0) + 1

    if not meths:
        st.info(t("coffee_time_no_orders"))
        return

    col_t1, col_t2 = st.columns([1, 4])
    with col_t1:
        mode = st.radio(
            t("radio_focus"),
            [t("radio_top_5"), t("radio_all")],
            horizontal=False,
            label_visibility="collapsed",
            key="meth_toggle",
        )

    s_meths = sorted(meths.items(), key=lambda x: x[1], reverse=True)
    total_count_all = sum(meths.values())

    if mode == t("radio_top_5"):
        s_meths_top = s_meths[:5]
        labels = [t(x[0]) for x in s_meths_top]
        values = [x[1] for x in s_meths_top]

        fig = go.Figure(
            data=[
                go.Pie(
                    labels=labels,
                    values=values,
                    hole=0.6,
                    marker=dict(
                        colors=[
                            COLORS["primary"],
                            COLORS["secondary"],
                            COLORS["accent"],
                            COLORS["success"],
                            COLORS["danger"],
                        ],
                        line=dict(color="#1A1715", width=2),
                    ),
                    textinfo="label+percent",
                    hoverinfo="label+value",
                )
            ]
        )

        fig.add_annotation(
            text=f"<b>{total_count_all}</b><br>{t('radio_analysis')}",
            x=0.5,
            y=0.5,
            font_size=18,
            showarrow=False,
            font_color=COLORS["text"],
        )

        fig.update_layout(CHART_LAYOUT_BASE)
        fig.update_layout(height=400, showlegend=False)

    else:
        df_plot = pd.DataFrame(
            s_meths, columns=[t("label_table_methods"), t("label_quantity")]
        )

        col_method = t("label_table_methods")
        col_count = t("label_quantity")
        df_plot = pd.DataFrame(s_meths, columns=[col_method, col_count])
        df_plot[col_method] = df_plot[col_method].apply(lambda x: t(x))
        fig = px.bar(
            df_plot, x=col_count, y=col_method, orientation="h", text=col_count
        )
        fig.update_layout(CHART_LAYOUT_BASE)
        fig.update_layout(
            height=max(400, len(df_plot) * 30),
            yaxis={"categoryorder": "total ascending", "title": ""},
            xaxis=dict(title=t("stat_samples"), dtick=1),
        )
        fig.update_traces(
            marker_color=COLORS["primary"],
            marker_line_width=0,
            textposition="outside",
            cliponaxis=False,
        )

    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


def render_flow_trends(df):
    """Auftragseingang der letzten 30 Tage."""
    st.markdown(f"#### 📈 {t('chart_trends')}")

    if df.empty:
        return

    df["date"] = pd.to_datetime(df["created_at"]).dt.date
    today = datetime.now().date()
    start_date = today - timedelta(days=30)

    trend_df = (
        df[df["date"] >= start_date].groupby("date").size().reset_index(name="count")
    )

    all_dates = pd.date_range(start=start_date, end=today).date
    trend_df = trend_df.set_index("date").reindex(all_dates, fill_value=0).reset_index()
    trend_df.columns = ["date", "count"]

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=trend_df["date"],
            y=trend_df["count"],
            mode="lines+markers",
            line=dict(shape="spline", width=3, color=COLORS["secondary"]),
            fill="tozeroy",
            fillcolor="rgba(137, 166, 179, 0.1)",
            marker=dict(
                size=6, color=COLORS["secondary"], line=dict(width=1, color="white")
            ),
            hovertemplate=f"<b>{t('label_date')}</b> %{{x|%d.%m.%Y}}<br><b>{t('label_orders')}</b> %{{y}}<extra></extra>",
        )
    )

    fig.update_layout(CHART_LAYOUT_BASE)
    fig.update_layout(
        height=300,
        yaxis=dict(dtick=1, tickformat="d", title=""),
        xaxis=dict(tickformat="%d.%m.", nticks=10),
    )
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


def render_status_funnel(df):
    """Pipeline-Status (Immer alle Status sichtbar, SOS-Design optimiert)."""
    st.markdown(f"#### 🚦 {t('chart_funnel')}")


    pipeline_df = df[df["status"].isin(logic.PIPELINE_STATUS_FLOW)].copy()
    counts = (
        pipeline_df["status"]
        .value_counts()
        .reindex(logic.PIPELINE_STATUS_FLOW, fill_value=0)
        .reset_index()
    )
    counts.columns = ["status", "count"]
    counts["display_name"] = counts["status"].apply(lambda x: t(x))


    max_val = counts["count"].max()

    x_range = [0, 5] if max_val == 0 else [0, None]


    fig = go.Figure(
        go.Bar(
            x=counts["count"],
            y=counts["display_name"],
            orientation="h",
            marker=dict(
                color=[
                    logic.STATUS_COLORS.get(s, COLORS["secondary"])
                    for s in counts["status"]
                ],
                line=dict(width=0),
            ),
            text=counts["count"],
            textposition="outside",

            cliponaxis=False,
        )
    )

    fig.update_layout(CHART_LAYOUT_BASE)


    fig.update_layout(
        height=350,
        margin=dict(r=40, l=10, t=10, b=10),  # Dieser Wert gewinnt jetzt!
        yaxis=dict(autorange="reversed", title="", type="category"),
        xaxis=dict(
            range=x_range,
            rangemode="nonnegative",
            title=t("total_orders"),
            dtick=1,
            zeroline=True,
            zerolinecolor="rgba(232, 227, 223, 0.2)",
        ),
    )


    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


def render_project_gravity(df):
    """Treemap für Projektgewichtung mit SOS-Farbgradient."""
    st.markdown(f"#### 🌍 {t('chart_gravity')}")

    archive_keys = [
        "cat_order_released",
        "cat_order_annulated",
    ]
    open_df = df[~df["status"].isin(archive_keys)].copy()


    proj_df = open_df.groupby("order_number")["sample_count"].sum().reset_index()
    proj_df = proj_df[proj_df["sample_count"] > 0]

    if proj_df.empty:
        st.info("404 - no orders found")
        return




    sos_gradient = [
        [0, "#9EB384"],  # Wenig Proben = Alles im grünen Bereich
        [1, "#D67B72"],  # Viele Proben = Achtung, hoher Workload!
    ]

    fig = px.treemap(
        proj_df,
        path=["order_number"],
        values="sample_count",
        color="sample_count",
        color_continuous_scale=sos_gradient,
    )


    fig.update_layout(CHART_LAYOUT_BASE)
    fig.update_layout(
        height=300,
        coloraxis_showscale=False,
        margin=dict(t=10, b=10, l=10, r=10),  # Knapperer Rand für kompaktes UI
    )

    fig.update_traces(
        textinfo="label+value",
        hovertemplate=f"<b>{t('cat_order')}:</b> %{{label}}<br><b>{t('cat_samples')}:</b> %{{value}}<extra></extra>",
        marker=dict(
            line=dict(width=1, color="#121212")
        ),  # Dunkle Trennlinie für den Darkmode
        textfont=dict(size=14),
    )

    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


def render_oldest_orders_table(df):
    """Die 5 ältesten offenen Aufträge als Tabelle."""
    st.markdown(f"#### ⏳ {t('header_list_commands')}")


    archive_keys = ["cat_order_released", "cat_order_annulated"]
    open_orders = df[~df["status"].isin(archive_keys)].copy()

    if open_orders.empty:
        st.success(t("info_successful_noorders"))
        return

    open_orders["days_open"] = (
        datetime.now() - pd.to_datetime(open_orders["created_at"])
    ).dt.days
    top_5 = open_orders.sort_values("days_open", ascending=False).head(5)


    top_5["status_display"] = top_5["status"].apply(lambda x: t(x))

    display_df = top_5[["order_number", "project_name", "status_display", "days_open"]]
    display_df.columns = [t("label_ID"), t("project"), t("status"), t("days_open")]

    st.dataframe(
        display_df,
        width="stretch",
        hide_index=True,
        column_config={t("days_open"): st.column_config.NumberColumn(format="%d d ⏳")},
    )
