"""
ChainFlow — Reports Page
Generate filtered reports with charts and Excel export.
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, datetime
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from database.db import init_database, get_supabase
from utils.helpers import (
    get_demand_df, get_current_stock, get_products_df,
    get_warehouses_df, format_number, apply_sidebar_filters,
)
from utils.excel_handler import export_to_excel
from utils.auth import check_login, require_role, get_current_user, render_sidebar_user_info

init_database()

css_path = os.path.join(os.path.dirname(__file__), "..", "assets", "style.css")
if os.path.exists(css_path):
    with open(css_path) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# ── Login + RBAC ──
user = check_login()
require_role(["admin", "warehouse_manager", "viewer"])
render_sidebar_user_info()

st.markdown("""
<div class="page-header">
    <h1>📈 Reports / رپورٹس</h1>
    <p>Generate detailed reports with filters, charts, and Excel export</p>
</div>
""", unsafe_allow_html=True)

filters = apply_sidebar_filters()

report_type = st.selectbox("Select Report / رپورٹ منتخب کریں", [
    "Monthly Demand Report",
    "Monthly Dispatch Report",
    "Pending Demand Report",
    "Stock Report",
    "Product-wise Report",
    "Warehouse-wise Report",
    "Year-on-Year Comparison",
])

st.markdown("---")

# ── Monthly Demand Report ──
if report_type == "Monthly Demand Report":
    st.subheader("📦 Monthly Demand Report")
    df = get_demand_df(filters)
    if not df.empty:
        mc1, mc2, mc3 = st.columns(3)
        mc1.metric("Total Demand", format_number(df["quantity"].sum()))
        mc2.metric("Total Delivered", format_number(df["delivered"].sum()))
        mc3.metric("Avg Delivery %", f"{df['delivery_pct'].mean():.1f}%")

        # Trend chart
        monthly = df.copy()
        monthly["month"] = pd.to_datetime(monthly["demand_date"]).dt.to_period("M").astype(str)
        trend = monthly.groupby("month").agg(Demand=("quantity", "sum"), Delivered=("delivered", "sum")).reset_index()

        fig = go.Figure()
        fig.add_trace(go.Scatter(x=trend["month"], y=trend["Demand"], name="Demand", mode="lines+markers",
                                 line=dict(color="#1565C0", width=2)))
        fig.add_trace(go.Scatter(x=trend["month"], y=trend["Delivered"], name="Delivered", mode="lines+markers",
                                 line=dict(color="#2E7D32", width=2)))
        fig.update_layout(height=350, margin=dict(t=20, b=40), legend=dict(orientation="h", y=1.1))
        st.plotly_chart(fig, use_container_width=True)

        display = df[["reference", "demand_date", "product_name", "warehouse_name",
                       "quantity", "delivered", "remaining", "delivery_pct", "status"]].copy()
        display.columns = ["Ref", "Date", "Product", "Warehouse", "Demand", "Delivered", "Remaining", "% Done", "Status"]
        st.dataframe(display, use_container_width=True, height=400)

        st.download_button("📥 Export", data=export_to_excel(display, "Monthly Demand"),
                           file_name=f"monthly_demand_{date.today()}.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    else:
        st.info("No data for selected filters.")

# ── Monthly Dispatch Report ──
elif report_type == "Monthly Dispatch Report":
    st.subheader("🚚 Monthly Dispatch Report")
    sb = get_supabase()

    # Query dispatch records
    query = sb.table("dispatch").select("dispatch_date, demand_id, product_id, warehouse_id, quantity").eq("is_deleted", 0)
    if filters.get("date_from"):
        query = query.gte("dispatch_date", str(filters["date_from"]))
    if filters.get("date_to"):
        query = query.lte("dispatch_date", str(filters["date_to"]))
    if filters.get("warehouse_id"):
        query = query.eq("warehouse_id", filters["warehouse_id"])
    query = query.order("dispatch_date", desc=True)
    result = query.execute()

    if result.data:
        df = pd.DataFrame(result.data)

        # Get demand references
        demand_ids = df["demand_id"].unique().tolist()
        if demand_ids:
            demands = sb.table("demand").select("id, reference").in_("id", demand_ids).execute()
            demand_map = {d["id"]: d["reference"] for d in demands.data} if demands.data else {}
            df["Demand Ref"] = df["demand_id"].map(demand_map)

        # Get product names
        product_ids = df["product_id"].unique().tolist()
        if product_ids:
            prods = sb.table("products").select("id, name").in_("id", product_ids).execute()
            prod_map = {p["id"]: p["name"] for p in prods.data} if prods.data else {}
            df["Product"] = df["product_id"].map(prod_map)

        # Get warehouse names
        wh_ids = df["warehouse_id"].unique().tolist()
        if wh_ids:
            whs = sb.table("warehouses").select("id, name").in_("id", wh_ids).execute()
            wh_map = {w["id"]: w["name"] for w in whs.data} if whs.data else {}
            df["Warehouse"] = df["warehouse_id"].map(wh_map)

        df.rename(columns={"dispatch_date": "Date", "quantity": "Quantity"}, inplace=True)
        display = df[["Date", "Demand Ref", "Product", "Warehouse", "Quantity"]]

        st.metric("Total Dispatched", format_number(display["Quantity"].sum()))

        fig = px.bar(display.groupby("Product")["Quantity"].sum().reset_index().nlargest(15, "Quantity"),
                     x="Product", y="Quantity", color_discrete_sequence=["#2E7D32"])
        fig.update_layout(height=350, margin=dict(t=20, b=40))
        st.plotly_chart(fig, use_container_width=True)

        st.dataframe(display, use_container_width=True, height=400)
        st.download_button("📥 Export", data=export_to_excel(display, "Dispatch Report"),
                           file_name=f"dispatch_report_{date.today()}.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    else:
        st.info("No dispatch data for selected filters.")

# ── Pending Demand Report ──
elif report_type == "Pending Demand Report":
    st.subheader("⏳ Pending Demand Report")
    df = get_demand_df(filters)
    if not df.empty:
        pending = df[df["status"].isin(["Pending", "Partially Dispatched"])].copy()
        if not pending.empty:
            st.metric("Total Pending Quantity", format_number(pending["remaining"].sum()))

            display = pending[["reference", "demand_date", "product_name", "warehouse_name",
                               "quantity", "delivered", "remaining", "delivery_pct", "status"]].copy()
            display.columns = ["Ref", "Date", "Product", "Warehouse", "Demand", "Delivered", "Remaining", "% Done", "Status"]
            st.dataframe(display, use_container_width=True, height=400)

            st.download_button("📥 Export", data=export_to_excel(display, "Pending Demand"),
                               file_name=f"pending_demand_{date.today()}.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        else:
            st.success("🎉 No pending demand! All orders fulfilled.")
    else:
        st.info("No demand data.")

# ── Stock Report ──
elif report_type == "Stock Report":
    st.subheader("🏭 Stock Report")
    stock_df = get_current_stock(
        warehouse_id=filters.get("warehouse_id"),
        product_id=filters.get("product_id"),
    )
    if not stock_df.empty:
        mc1, mc2, mc3 = st.columns(3)
        mc1.metric("Total Stock", format_number(stock_df["current_stock"].sum()))
        mc2.metric("🔴 Critical", len(stock_df[stock_df["stock_status"].str.contains("Critical")]))
        mc3.metric("🟡 Low", len(stock_df[stock_df["stock_status"].str.contains("Low")]))

        display = stock_df[["product_name", "warehouse_name", "current_stock",
                            "buffer_stock", "minimum_stock", "stock_status"]].copy()
        display.columns = ["Product", "Warehouse", "Current Stock", "Buffer", "Minimum", "Status"]

        st.dataframe(display, use_container_width=True, height=400)
        st.download_button("📥 Export", data=export_to_excel(display, "Stock Report"),
                           file_name=f"stock_report_{date.today()}.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    else:
        st.info("No stock data available.")

# ── Product-wise Report ──
elif report_type == "Product-wise Report":
    st.subheader("🧪 Product-wise Summary")
    df = get_demand_df(filters)
    if not df.empty:
        summary = df.groupby("product_name").agg(
            Total_Demand=("quantity", "sum"),
            Total_Delivered=("delivered", "sum"),
            Total_Remaining=("remaining", "sum"),
            Orders=("id", "count"),
        ).reset_index()
        summary["Delivery_%"] = (summary["Total_Delivered"] / summary["Total_Demand"] * 100).round(1)
        summary.columns = ["Product", "Demand", "Delivered", "Remaining", "Orders", "Delivery %"]

        fig = px.bar(summary.nlargest(15, "Demand"), x="Product", y=["Demand", "Delivered"],
                     barmode="group", color_discrete_sequence=["#1565C0", "#2E7D32"])
        fig.update_layout(height=350, margin=dict(t=20, b=40))
        st.plotly_chart(fig, use_container_width=True)

        st.dataframe(summary, use_container_width=True, height=400)
        st.download_button("📥 Export", data=export_to_excel(summary, "Product Summary"),
                           file_name=f"product_report_{date.today()}.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    else:
        st.info("No demand data.")

# ── Warehouse-wise Report ──
elif report_type == "Warehouse-wise Report":
    st.subheader("🏢 Warehouse-wise Summary")
    df = get_demand_df(filters)
    if not df.empty:
        summary = df.groupby("warehouse_name").agg(
            Total_Demand=("quantity", "sum"),
            Total_Delivered=("delivered", "sum"),
            Total_Remaining=("remaining", "sum"),
            Orders=("id", "count"),
        ).reset_index()
        summary["Delivery_%"] = (summary["Total_Delivered"] / summary["Total_Demand"] * 100).round(1)
        summary.columns = ["Warehouse", "Demand", "Delivered", "Remaining", "Orders", "Delivery %"]

        fig = px.pie(summary, names="Warehouse", values="Demand", title="Demand Distribution",
                     color_discrete_sequence=px.colors.qualitative.Set2)
        fig.update_layout(height=350, margin=dict(t=40, b=20))
        st.plotly_chart(fig, use_container_width=True)

        st.dataframe(summary, use_container_width=True, height=400)
        st.download_button("📥 Export", data=export_to_excel(summary, "Warehouse Summary"),
                           file_name=f"warehouse_report_{date.today()}.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    else:
        st.info("No demand data.")

# ── Year-on-Year Comparison ──
elif report_type == "Year-on-Year Comparison":
    st.subheader("📊 Year-on-Year Comparison / سالانہ موازنہ")
    year = st.number_input("Compare Year", min_value=2020, max_value=2030, value=date.today().year)
    prev_year = year - 1

    # Get current year data using demand_detail view
    current_filters = {"year": year}
    if filters.get("warehouse_id"):
        current_filters["warehouse_id"] = filters["warehouse_id"]
    current_df = get_demand_df(current_filters)

    prev_filters = {"year": prev_year}
    if filters.get("warehouse_id"):
        prev_filters["warehouse_id"] = filters["warehouse_id"]
    prev_df = get_demand_df(prev_filters)

    if not current_df.empty or not prev_df.empty:
        months = [f"{i:02d}" for i in range(1, 13)]
        month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

        fig = go.Figure()

        if not current_df.empty:
            current_df["month"] = pd.to_datetime(current_df["demand_date"]).dt.strftime("%m")
            cur_agg = current_df.groupby("month").agg(demand=("quantity", "sum"), delivered=("delivered", "sum")).reindex(months).fillna(0)
            fig.add_trace(go.Bar(x=month_names, y=cur_agg["demand"], name=f"Demand {year}", marker_color="#1565C0"))

        if not prev_df.empty:
            prev_df["month"] = pd.to_datetime(prev_df["demand_date"]).dt.strftime("%m")
            prev_agg = prev_df.groupby("month").agg(demand=("quantity", "sum"), delivered=("delivered", "sum")).reindex(months).fillna(0)
            fig.add_trace(go.Bar(x=month_names, y=prev_agg["demand"], name=f"Demand {prev_year}", marker_color="#90CAF9"))

        fig.update_layout(barmode="group", height=400, margin=dict(t=20, b=40))
        st.plotly_chart(fig, use_container_width=True)

        # Growth table
        if not current_df.empty and not prev_df.empty:
            merged = cur_agg.join(prev_agg, lsuffix=f"_{year}", rsuffix=f"_{prev_year}", how="outer").fillna(0)
            merged[f"Growth_%"] = ((merged[f"demand_{year}"] - merged[f"demand_{prev_year}"]) / merged[f"demand_{prev_year}"].replace(0, 1) * 100).round(1)
            merged.index = [month_names[int(m)-1] for m in merged.index]
            st.dataframe(merged, use_container_width=True)

            st.download_button("📥 Export", data=export_to_excel(merged.reset_index(), "YoY Comparison"),
                               file_name=f"yoy_comparison_{year}.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    else:
        st.info("No data available for comparison.")
