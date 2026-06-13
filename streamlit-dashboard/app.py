import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
from pathlib import Path

st.set_page_config(
    page_title="Last Mile Delivery Auditor — Veridi Logistics",
    page_icon="🚚",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Data loading — STORY 1: Schema Builder
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner="Loading & joining 96K+ orders…")
def load_data():
    orders = pd.read_csv("../olist_orders_dataset.csv")
    reviews = pd.read_csv("../olist_order_reviews_dataset.csv")
    customers = pd.read_csv("../olist_customers_dataset.csv")
    items = pd.read_csv("../olist_order_items_dataset.csv")
    products = pd.read_csv("../olist_products_dataset.csv")
    translations = pd.read_csv("../product_category_name_translation.csv")

    # Aggregate reviews: one row per order (prevent 1-to-many row explosion)
    reviews_agg = (
        reviews.groupby("order_id", as_index=False)
        .agg(review_score=("review_score", "mean"))
    )

    # First item per order for category lookup
    items_first = (
        items.sort_values("order_item_id")
        .groupby("order_id", as_index=False)
        .first()[["order_id", "product_id"]]
    )

    # Merge products with English translations (BONUS: Translation Challenge)
    products = products.merge(translations, on="product_category_name", how="left")

    # Build master dataset
    df = orders.merge(reviews_agg, on="order_id", how="left")
    df = df.merge(
        customers[["customer_id", "customer_state", "customer_city"]],
        on="customer_id", how="left",
    )
    df = df.merge(items_first, on="order_id", how="left")
    df = df.merge(
        products[["product_id", "product_category_name", "product_category_name_english"]],
        on="product_id", how="left",
    )

    # Exclude canceled / unavailable (per acceptance criteria)
    df = df[~df["order_status"].isin(["canceled", "unavailable"])].copy()

    # -----------------------------------------------------------------------
    # STORY 2: Delay Calculator
    # Days_Difference = estimated − actual  (positive = early, negative = late)
    # -----------------------------------------------------------------------
    df["order_estimated_delivery_date"] = pd.to_datetime(df["order_estimated_delivery_date"])
    df["order_delivered_customer_date"] = pd.to_datetime(df["order_delivered_customer_date"])
    df["order_purchase_timestamp"] = pd.to_datetime(df["order_purchase_timestamp"])

    df["days_difference"] = (
        df["order_estimated_delivery_date"] - df["order_delivered_customer_date"]
    ).dt.days

    def classify(d):
        if pd.isna(d):
            return "Not Delivered"
        elif d >= 0:
            return "On Time"
        elif d >= -5:
            return "Late"
        else:
            return "Super Late"

    df["delivery_status"] = df["days_difference"].apply(classify)
    df["year_month"] = df["order_purchase_timestamp"].dt.to_period("M").astype(str)
    df["year"] = df["order_purchase_timestamp"].dt.year

    # Drop rows without delivery date for metric calculations
    df_delivered = df[df["delivery_status"] != "Not Delivered"].copy()

    return df, df_delivered


df_all, df = load_data()

# ---------------------------------------------------------------------------
# Sidebar filters
# ---------------------------------------------------------------------------
st.sidebar.image(
    "https://img.icons8.com/color/96/truck.png",
    width=60,
)
st.sidebar.title("Veridi Logistics")
st.sidebar.caption("Last Mile Delivery Auditor")
st.sidebar.divider()

status_options = ["All", "On Time", "Late", "Super Late"]
selected_status = st.sidebar.selectbox("Delivery Status", status_options)

all_states = sorted(df["customer_state"].dropna().unique())
selected_states = st.sidebar.multiselect(
    "Filter by State", all_states, default=[], placeholder="All states"
)

min_date = df["order_purchase_timestamp"].min().date()
max_date = df["order_purchase_timestamp"].max().date()
date_range = st.sidebar.date_input(
    "Purchase Date Range",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date,
)

st.sidebar.divider()
st.sidebar.caption("📦 Olist E-Commerce Dataset · 2016–2018")
st.sidebar.caption("🇧🇷 Brazilian marketplace, 96K+ orders")

# Apply filters
filtered = df.copy()
if selected_status != "All":
    filtered = filtered[filtered["delivery_status"] == selected_status]
if selected_states:
    filtered = filtered[filtered["customer_state"].isin(selected_states)]
if len(date_range) == 2:
    start, end = date_range
    filtered = filtered[
        (filtered["order_purchase_timestamp"].dt.date >= start)
        & (filtered["order_purchase_timestamp"].dt.date <= end)
    ]

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.title("🚚 Last Mile Delivery Audit")
st.markdown(
    "**Veridi Logistics** · Olist Brazilian E-Commerce · 2016–2018 · "
    "Classified by *Estimated vs Actual Delivery Date*"
)
st.divider()

# ---------------------------------------------------------------------------
# KPI Cards
# ---------------------------------------------------------------------------
total = len(filtered)
on_time = (filtered["delivery_status"] == "On Time").sum()
late = (filtered["delivery_status"] == "Late").sum()
super_late = (filtered["delivery_status"] == "Super Late").sum()
avg_review = filtered["review_score"].mean()
avg_delay = filtered[filtered["days_difference"] < 0]["days_difference"].mean()

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Total Orders", f"{total:,}", help="Delivered orders (excl. canceled/unavailable)")
c2.metric("On Time", f"{on_time/total*100:.1f}%" if total else "—", f"{on_time:,} orders")
c3.metric("Late (1–5d)", f"{late/total*100:.1f}%" if total else "—", f"{late:,} orders")
c4.metric("Super Late (>5d)", f"{super_late/total*100:.1f}%" if total else "—", f"{super_late:,} orders", delta_color="inverse")
c5.metric("Avg Review Score", f"{avg_review:.2f} / 5" if not np.isnan(avg_review) else "—",
          f"Avg delay: {avg_delay:.1f}d" if not np.isnan(avg_delay) else None, delta_color="inverse")

st.divider()

# ---------------------------------------------------------------------------
# STORY 3: Geographic Heatmap — % Late by State
# ---------------------------------------------------------------------------
st.subheader("📍 Story 3 · Geographic Analysis — % Late Deliveries by State")
st.caption(
    "Which states have the worst on-time rates? Remote states far from São Paulo's "
    "distribution hub are disproportionately affected."
)

state_stats = (
    df.groupby("customer_state")
    .agg(
        total=("order_id", "count"),
        on_time=("delivery_status", lambda x: (x == "On Time").sum()),
        late=("delivery_status", lambda x: (x == "Late").sum()),
        super_late=("delivery_status", lambda x: (x == "Super Late").sum()),
        avg_review=("review_score", "mean"),
    )
    .reset_index()
)
state_stats["pct_late"] = (state_stats["late"] + state_stats["super_late"]) / state_stats["total"] * 100
state_stats["pct_on_time"] = state_stats["on_time"] / state_stats["total"] * 100
state_stats = state_stats.sort_values("pct_late", ascending=False)

col_geo1, col_geo2 = st.columns([2, 1])

with col_geo1:
    color_map = {"On Time": "#22c55e", "Late": "#f59e0b", "Super Late": "#ef4444"}
    fig_state = px.bar(
        state_stats,
        x="customer_state",
        y=["pct_on_time", "pct_late"],
        title="% Late Deliveries by Brazilian State",
        labels={"value": "% of Orders", "customer_state": "State", "variable": ""},
        color_discrete_map={
            "pct_on_time": "#22c55e",
            "pct_late": "#ef4444",
        },
        barmode="stack",
        height=420,
    )
    fig_state.update_layout(
        legend=dict(orientation="h", y=-0.2),
        xaxis_title="Brazilian State",
        yaxis_title="% of Orders",
        plot_bgcolor="white",
        yaxis=dict(ticksuffix="%"),
    )
    fig_state.for_each_trace(lambda t: t.update(
        name="On Time" if "on_time" in t.name else "Late / Super Late"
    ))
    st.plotly_chart(fig_state, use_container_width=True)

with col_geo2:
    st.dataframe(
        state_stats[["customer_state", "total", "pct_on_time", "pct_late", "avg_review"]]
        .rename(columns={
            "customer_state": "State",
            "total": "Orders",
            "pct_on_time": "On Time %",
            "pct_late": "Late %",
            "avg_review": "Avg Score",
        })
        .assign(**{
            "On Time %": lambda d: d["On Time %"].round(1),
            "Late %": lambda d: d["Late %"].round(1),
            "Avg Score": lambda d: d["Avg Score"].round(2),
        }),
        hide_index=True,
        height=420,
        use_container_width=True,
    )

st.divider()

# ---------------------------------------------------------------------------
# STORY 4: Sentiment Correlation — Delay vs Review Score
# ---------------------------------------------------------------------------
st.subheader("⭐ Story 4 · Sentiment Correlation — Delivery Delay vs Review Score")
st.caption(
    "Late deliveries drive negative reviews. On-time orders average 4.3★ vs 2.3★ for Super Late."
)

col_s1, col_s2 = st.columns(2)

with col_s1:
    sentiment_avg = (
        filtered.groupby("delivery_status")["review_score"]
        .mean()
        .reset_index()
        .rename(columns={"delivery_status": "Status", "review_score": "Avg Review Score"})
    )
    order_map = {"On Time": 0, "Late": 1, "Super Late": 2, "Not Delivered": 3}
    sentiment_avg = sentiment_avg.sort_values(
        "Status", key=lambda s: s.map(order_map).fillna(99)
    )
    status_colors = {
        "On Time": "#22c55e",
        "Late": "#f59e0b",
        "Super Late": "#ef4444",
        "Not Delivered": "#94a3b8",
    }
    fig_sent = px.bar(
        sentiment_avg,
        x="Status",
        y="Avg Review Score",
        color="Status",
        color_discrete_map=status_colors,
        title="Average Review Score by Delivery Status",
        range_y=[1, 5],
        height=350,
        text_auto=".2f",
    )
    fig_sent.update_layout(showlegend=False, plot_bgcolor="white",
                           yaxis=dict(tickvals=[1,2,3,4,5]))
    fig_sent.update_traces(textposition="outside")
    st.plotly_chart(fig_sent, use_container_width=True)

with col_s2:
    # Bucket delay days and show avg review
    delay_df = filtered[filtered["days_difference"].notna()].copy()
    delay_df["delay_bucket"] = pd.cut(
        delay_df["days_difference"],
        bins=[-999, -30, -20, -10, -5, -1, 0, 10, 20, 999],
        labels=[">30d Late", "21-30d Late", "11-20d Late", "6-10d Late",
                "1-5d Late", "On Time (0d)", "1-10d Early", "11-20d Early", ">20d Early"],
    )
    bucket_avg = (
        delay_df.groupby("delay_bucket", observed=True)["review_score"]
        .agg(["mean", "count"])
        .reset_index()
        .rename(columns={"mean": "Avg Review", "count": "Orders", "delay_bucket": "Delay Bucket"})
    )
    fig_bucket = px.bar(
        bucket_avg,
        x="Delay Bucket",
        y="Avg Review",
        title="Review Score by Delay Bucket",
        color="Avg Review",
        color_continuous_scale=["#ef4444", "#f59e0b", "#22c55e"],
        range_y=[1, 5],
        height=350,
        text_auto=".2f",
    )
    fig_bucket.update_layout(showlegend=False, plot_bgcolor="white",
                              coloraxis_showscale=False,
                              yaxis=dict(tickvals=[1,2,3,4,5]))
    fig_bucket.update_traces(textposition="outside")
    st.plotly_chart(fig_bucket, use_container_width=True)

st.divider()

# ---------------------------------------------------------------------------
# BONUS: Category Translation Challenge
# ---------------------------------------------------------------------------
st.subheader("📦 Bonus · Category Analysis — On-Time Rate by Product Category (English)")
st.caption(
    "Categories with bulky/heavy items (furniture, appliances) show lower on-time rates. "
    "Electronics and small items ship more reliably."
)

cat_stats = (
    df.groupby("product_category_name_english")
    .agg(
        total=("order_id", "count"),
        on_time=("delivery_status", lambda x: (x == "On Time").sum()),
        avg_review=("review_score", "mean"),
    )
    .reset_index()
)
cat_stats["on_time_pct"] = cat_stats["on_time"] / cat_stats["total"] * 100
cat_stats = cat_stats[cat_stats["total"] >= 200].sort_values("on_time_pct", ascending=True)
cat_stats["label"] = cat_stats["product_category_name_english"].str.replace("_", " ").str.title()

fig_cat = px.bar(
    cat_stats.tail(30),
    y="label",
    x="on_time_pct",
    orientation="h",
    color="on_time_pct",
    color_continuous_scale=["#ef4444", "#f59e0b", "#22c55e"],
    title="Top 30 Categories by On-Time Rate (min 200 orders)",
    labels={"on_time_pct": "On-Time %", "label": "Category"},
    height=700,
    text_auto=".1f",
)
fig_cat.update_layout(
    plot_bgcolor="white",
    coloraxis_showscale=False,
    xaxis=dict(ticksuffix="%", range=[0, 105]),
)
fig_cat.update_traces(textposition="outside", texttemplate="%{x:.1f}%")
st.plotly_chart(fig_cat, use_container_width=True)

st.divider()

# ---------------------------------------------------------------------------
# CANDIDATE'S CHOICE: Monthly Delivery Performance Trend
# Justification: Reveals whether the CEO's observed spike is a recent trend
# or a persistent structural issue — critical for root cause analysis.
# ---------------------------------------------------------------------------
st.subheader("📈 Candidate's Choice · Monthly Delivery Performance Trend")
st.info(
    "**Business Justification:** The CEO suspects a *spike* in negative reviews. "
    "This chart reveals whether late deliveries are a worsening trend or a longstanding "
    "structural issue — answering whether the root cause is operational drift or a systemic flaw. "
    "It also shows seasonality peaks (e.g., holiday sales volumes straining logistics capacity)."
)

monthly = (
    df.groupby("year_month")
    .agg(
        total=("order_id", "count"),
        on_time=("delivery_status", lambda x: (x == "On Time").sum()),
        late=("delivery_status", lambda x: (x == "Late").sum()),
        super_late=("delivery_status", lambda x: (x == "Super Late").sum()),
        avg_review=("review_score", "mean"),
    )
    .reset_index()
    .sort_values("year_month")
)
monthly["pct_on_time"] = monthly["on_time"] / monthly["total"] * 100
monthly["pct_late"] = monthly["late"] / monthly["total"] * 100
monthly["pct_super_late"] = monthly["super_late"] / monthly["total"] * 100

fig_monthly = go.Figure()
fig_monthly.add_trace(go.Scatter(
    x=monthly["year_month"], y=monthly["pct_on_time"],
    name="On Time %", mode="lines+markers",
    line=dict(color="#22c55e", width=2),
    fill="tozeroy", fillcolor="rgba(34,197,94,0.1)",
))
fig_monthly.add_trace(go.Scatter(
    x=monthly["year_month"], y=monthly["pct_late"],
    name="Late %", mode="lines+markers",
    line=dict(color="#f59e0b", width=2),
))
fig_monthly.add_trace(go.Scatter(
    x=monthly["year_month"], y=monthly["pct_super_late"],
    name="Super Late %", mode="lines+markers",
    line=dict(color="#ef4444", width=2),
))
fig_monthly.add_trace(go.Scatter(
    x=monthly["year_month"], y=monthly["avg_review"] * 20,
    name="Avg Review ×20 (right scale)", mode="lines",
    line=dict(color="#8b5cf6", width=2, dash="dot"),
    yaxis="y2",
))
fig_monthly.update_layout(
    title="Monthly Delivery Performance & Review Score Trend",
    xaxis_title="Month",
    yaxis=dict(title="% of Orders", ticksuffix="%", range=[0, 105]),
    yaxis2=dict(
        title="Avg Review Score",
        overlaying="y", side="right",
        range=[0, 100], tickvals=[20,40,60,80,100],
        ticktext=["1.0","2.0","3.0","4.0","5.0"],
    ),
    height=420,
    plot_bgcolor="white",
    legend=dict(orientation="h", y=-0.2),
    hovermode="x unified",
)
st.plotly_chart(fig_monthly, use_container_width=True)

st.divider()

# ---------------------------------------------------------------------------
# Raw Data Explorer
# ---------------------------------------------------------------------------
with st.expander("🔍 Raw Data Explorer (filtered view)", expanded=False):
    show_cols = [
        "order_id", "order_status", "customer_state", "delivery_status",
        "days_difference", "review_score", "product_category_name_english",
        "order_purchase_timestamp", "order_estimated_delivery_date",
        "order_delivered_customer_date",
    ]
    display_df = filtered[show_cols].rename(columns={
        "order_id": "Order ID",
        "order_status": "Status",
        "customer_state": "State",
        "delivery_status": "Delivery Class",
        "days_difference": "Days Diff",
        "review_score": "Review",
        "product_category_name_english": "Category",
        "order_purchase_timestamp": "Purchase Date",
        "order_estimated_delivery_date": "Est. Delivery",
        "order_delivered_customer_date": "Actual Delivery",
    })
    st.dataframe(display_df.head(500), use_container_width=True, hide_index=True)
    csv_data = display_df.to_csv(index=False)
    st.download_button(
        "⬇️ Download Filtered CSV",
        csv_data,
        "delivery_audit_filtered.csv",
        "text/csv",
    )

st.caption(
    "Veridi Logistics · Last Mile Delivery Auditor · "
    "Data: Olist Brazilian E-Commerce Public Dataset · Built with Streamlit"
)
