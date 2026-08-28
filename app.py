"""
ChainFlow — Supply Chain Dashboard for Pesticide Company
Main Dashboard / Home Page
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, datetime
import os, sys, base64

# ── Page Config ──
st.set_page_config(
    page_title="ChainFlow — Supply Chain Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Add project root to path ──
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import APP_NAME, APP_VERSION, COMPANY_NAME, JPL_LOGO_B64, get_label
from database.db import init_database, get_supabase, get_setting
from utils.helpers import (
    get_demand_df, get_current_stock, get_pending_demand,
    get_attention_products, format_number, apply_sidebar_filters,
    get_products_df, get_warehouses_df,
)
from utils.auth import check_login, render_sidebar_user_info, get_current_user

# ── Initialize Database ──
init_database()

# ── Load CSS ──
css_path = os.path.join(os.path.dirname(__file__), "assets", "style.css")
if os.path.exists(css_path):
    with open(css_path) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# ── Login Gate ──
user = check_login()

# ── Sidebar Branding ──
logo_html = f'<img src="data:image/png;base64,{JPL_LOGO_B64}" style="width:80px;height:auto;margin:0 auto;display:block;">'
st.sidebar.markdown(f"""
<div style="text-align:center; padding: 1rem 0;">
    {logo_html}
    <h2 style="color:#4CAF50; margin:0.5rem 0 0 0;">{APP_NAME}</h2>
    <p style="font-size:0.75rem; color:#888; margin:0;">{COMPANY_NAME}</p>
    <p style="font-size:0.8rem; color:#888;">v{APP_VERSION}</p>
</div>
""", unsafe_allow_html=True)

render_sidebar_user_info()

filters = apply_sidebar_filters()
bilingual = get_setting("language", "both") in ("both", "ur")

# ── Page Header ──
company = get_setting("company_name", "My Pesticide Company")
st.markdown(f"""
<div class="page-header">
    <h1>📊 {get_label('dashboard', bilingual)}</h1>
    <p>{company} — {date.today().strftime('%B %d, %Y')}</p>
</div>
""", unsafe_allow_html=True)

# ── Load Data ──
demand_df = get_demand_df(filters)
stock_df = get_current_stock(
    warehouse_id=filters.get("warehouse_id"),
    product_id=filters.get("product_id"),
)

# ── KPI Cards ──
total_demand = demand_df["quantity"].sum() if not demand_df.empty else 0
total_delivered = demand_df["delivered"].sum() if not demand_df.empty else 0
total_remaining = demand_df["remaining"].sum() if not demand_df.empty else 0
total_stock = stock_df["current_stock"].sum() if not stock_df.empty else 0
low_stock_count = len(stock_df[stock_df["stock_status"].str.contains("Critical|Low")]) if not stock_df.empty else 0
attention_items = get_attention_products()

col1, col2, col3, col4, col5, col6 = st.columns(6)

with col1:
    st.markdown(f"""
    <div class="kpi-card blue">
        <h3>{get_label('total_demand', bilingual)}</h3>
        <h2>{format_number(total_demand)}</h2>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown(f"""
    <div class="kpi-card green">
        <h3>{get_label('delivered', bilingual)}</h3>
        <h2>{format_number(total_delivered)}</h2>
    </div>
    """, unsafe_allow_html=True)

with col3:
    st.markdown(f"""
    <div class="kpi-card orange">
        <h3>{get_label('pending', bilingual)}</h3>
        <h2>{format_number(total_remaining)}</h2>
    </div>
    """, unsafe_allow_html=True)

with col4:
    st.markdown(f"""
    <div class="kpi-card blue">
        <h3>{get_label('current_stock', bilingual)}</h3>
        <h2>{format_number(total_stock)}</h2>
    </div>
    """, unsafe_allow_html=True)

with col5:
    card_class = "red" if low_stock_count > 0 else "green"
    st.markdown(f"""
    <div class="kpi-card {card_class}">
        <h3>{get_label('low_stock', bilingual)}</h3>
        <h2>{low_stock_count} Products</h2>
    </div>
    """, unsafe_allow_html=True)

with col6:
    card_class = "red" if len(attention_items) > 0 else "green"
    st.markdown(f"""
    <div class="kpi-card {card_class}">
        <h3>{get_label('attention', bilingual)}</h3>
        <h2>{len(attention_items)}</h2>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<div class='section-divider'></div>", unsafe_allow_html=True)

# ── Year-on-Year Comparison ──
if filters.get("compare_yoy") and not demand_df.empty:
    st.subheader("📊 Year-on-Year Comparison / سالانہ موازنہ")
    current_year = filters.get("year", date.today().year)
    prev_filters = {**filters, "year": current_year - 1}
    prev_df = get_demand_df(prev_filters)

    c1, c2, c3, c4 = st.columns(4)
    prev_demand = prev_df["quantity"].sum() if not prev_df.empty else 0
    prev_delivered = prev_df["delivered"].sum() if not prev_df.empty else 0

    growth_demand = ((total_demand - prev_demand) / prev_demand * 100) if prev_demand > 0 else 0
    growth_delivered = ((total_delivered - prev_delivered) / prev_delivered * 100) if prev_delivered > 0 else 0

    c1.metric(f"Demand {current_year}", format_number(total_demand), f"{growth_demand:+.1f}%")
    c2.metric(f"Demand {current_year - 1}", format_number(prev_demand))
    c3.metric(f"Delivered {current_year}", format_number(total_delivered), f"{growth_delivered:+.1f}%")
    c4.metric(f"Delivered {current_year - 1}", format_number(prev_delivered))

    st.markdown("<div class='section-divider'></div>", unsafe_allow_html=True)

# ── Charts ──
chart_col1, chart_col2 = st.columns(2)

with chart_col1:
    st.subheader("📦 Demand vs Delivered")
    if not demand_df.empty:
        chart_data = demand_df.groupby("product_name").agg(
            Demand=("quantity", "sum"),
            Delivered=("delivered", "sum"),
        ).head(15).reset_index()

        fig = go.Figure()
        fig.add_trace(go.Bar(name="Demand / ڈیمانڈ", x=chart_data["product_name"], y=chart_data["Demand"],
                             marker_color="#1565C0"))
        fig.add_trace(go.Bar(name="Delivered / فراہم", x=chart_data["product_name"], y=chart_data["Delivered"],
                             marker_color="#2E7D32"))
        fig.update_layout(barmode="group", height=350, margin=dict(t=20, b=40),
                          legend=dict(orientation="h", y=1.1))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No demand data available for the selected filters.")

with chart_col2:
    st.subheader("🏭 Stock by Product")
    if not stock_df.empty:
        stock_chart = stock_df.nlargest(15, "current_stock")
        colors = stock_chart["stock_status"].apply(
            lambda s: "#C62828" if "Critical" in s else "#F9A825" if "Low" in s else "#2E7D32"
        ).tolist()
        fig2 = go.Figure(go.Bar(
            x=stock_chart["product_name"], y=stock_chart["current_stock"],
            marker_color=colors,
        ))
        fig2.update_layout(height=350, margin=dict(t=20, b=40))
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("No stock data available. Add stock transactions first.")

st.markdown("<div class='section-divider'></div>", unsafe_allow_html=True)

# ── Demand vs Delivery Table ──
st.subheader(f"📋 {get_label('demand', bilingual)} vs Delivery Detail")

if not demand_df.empty:
    display_df = demand_df[[
        "product_name", "warehouse_name", "quantity", "delivered",
        "remaining", "delivery_pct", "status", "demand_date"
    ]].copy()
    display_df.columns = [
        "Product", "Warehouse", "Demand", "Delivered",
        "Remaining", "% Delivered", "Status", "Demand Date"
    ]

    def color_status(val):
        if val == "Fully Dispatched":
            return "background-color: #E8F5E9; color: #2E7D32"
        elif val == "Partially Dispatched":
            return "background-color: #FFF8E1; color: #E65100"
        elif val == "Cancelled":
            return "background-color: #F5F5F5; color: #757575"
        return "background-color: #FFEBEE; color: #C62828"

    styled = display_df.style.map(color_status, subset=["Status"])
    st.dataframe(styled, use_container_width=True, height=400)
else:
    st.info("No demand records found. Go to **Demand** page to add records.")

st.markdown("<div class='section-divider'></div>", unsafe_allow_html=True)

# ── Stock Status ──
st.subheader(f"🏭 {get_label('current_stock', bilingual)} Status")

if not stock_df.empty:
    stock_display = stock_df[[
        "product_name", "warehouse_name", "current_stock",
        "buffer_stock", "minimum_stock", "stock_status"
    ]].copy()
    stock_display.columns = ["Product", "Warehouse", "Current Stock", "Buffer Stock", "Minimum Stock", "Status"]

    def color_stock(val):
        if "Critical" in str(val):
            return "background-color: #FFEBEE; color: #C62828; font-weight: bold"
        elif "Low" in str(val):
            return "background-color: #FFF8E1; color: #E65100; font-weight: bold"
        return "background-color: #E8F5E9; color: #2E7D32"

    styled_stock = stock_display.style.map(color_stock, subset=["Status"])
    st.dataframe(styled_stock, use_container_width=True, height=350)
else:
    st.info("No stock data. Go to **Stock** page to add transactions.")

st.markdown("<div class='section-divider'></div>", unsafe_allow_html=True)

# ── Low Stock Alerts ──
if not stock_df.empty:
    critical = stock_df[stock_df["stock_status"].str.contains("Critical")]
    if not critical.empty:
        st.subheader("🚨 Low Stock Alerts / کم اسٹاک الرٹ")
        for _, row in critical.iterrows():
            st.markdown(f"""
            <div class="alert-box critical">
                <strong>🚨 LOW STOCK ALERT</strong><br>
                Product: <strong>{row['product_name']}</strong><br>
                Warehouse: {row['warehouse_name']}<br>
                Current Stock: <strong>{row['current_stock']:.0f}</strong> |
                Minimum Stock: {row['minimum_stock']:.0f}
            </div>
            """, unsafe_allow_html=True)

# ── Products Requiring Attention ──
if attention_items:
    st.subheader(f"⚠️ {get_label('attention', bilingual)}")
    for item in attention_items[:10]:
        severity_class = "critical" if item["severity"] == "high" else "warning"
        icon = "🚨" if item["severity"] == "high" else "⚠️"
        st.markdown(f"""
        <div class="alert-box {severity_class}">
            {icon} <strong>{item['product']}</strong> — {item['warehouse']}<br>
            {item['reason']}
        </div>
        """, unsafe_allow_html=True)

# ── Warehouse Comparison (Admin Only) ──
if user.get("role") == "admin":
    st.markdown("<div class='section-divider'></div>", unsafe_allow_html=True)
    st.subheader("🏢 Warehouse Comparison / گودام کا موازنہ")

    all_demand_df = get_demand_df({})
    all_stock_df = get_current_stock()

    if not all_demand_df.empty:
        wh_summary = all_demand_df.groupby("warehouse_name").agg(
            Total_Demand=("quantity", "sum"),
            Delivered=("delivered", "sum"),
            Pending=("remaining", "sum"),
        ).reset_index()

        if not all_stock_df.empty:
            stock_by_wh = all_stock_df.groupby("warehouse_name")["current_stock"].sum().reset_index()
            stock_by_wh.columns = ["warehouse_name", "Stock"]
            wh_summary = wh_summary.merge(stock_by_wh, on="warehouse_name", how="left")
        else:
            wh_summary["Stock"] = 0
        wh_summary["Stock"] = wh_summary["Stock"].fillna(0)

        comp_col1, comp_col2 = st.columns([2, 1])

        with comp_col1:
            fig_wh = go.Figure()
            fig_wh.add_trace(go.Bar(name="Demand / ڈیمانڈ", x=wh_summary["warehouse_name"],
                                     y=wh_summary["Total_Demand"], marker_color="#1565C0"))
            fig_wh.add_trace(go.Bar(name="Delivered / فراہم", x=wh_summary["warehouse_name"],
                                     y=wh_summary["Delivered"], marker_color="#2E7D32"))
            fig_wh.add_trace(go.Bar(name="Pending / زیرِ التوا", x=wh_summary["warehouse_name"],
                                     y=wh_summary["Pending"], marker_color="#E65100"))
            fig_wh.update_layout(barmode="group", height=380, margin=dict(t=20, b=40),
                                  legend=dict(orientation="h", y=1.12))
            st.plotly_chart(fig_wh, use_container_width=True)

        with comp_col2:
            table_display = wh_summary.copy()
            table_display.columns = ["Warehouse", "Total Demand", "Delivered", "Pending", "Stock"]
            for c in ["Total Demand", "Delivered", "Pending", "Stock"]:
                table_display[c] = table_display[c].apply(lambda v: format_number(v))
            st.dataframe(table_display, use_container_width=True, height=380, hide_index=True)
    else:
        st.info("No demand data available across warehouses yet.")

# ── Footer ──
st.markdown("---")
st.caption(f"{APP_NAME} v{APP_VERSION} — Built for {company}")
