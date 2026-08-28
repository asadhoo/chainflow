"""
ChainFlow — Stock Management Page
Track stock levels, add transactions, view stock status.
"""
import streamlit as st
import pandas as pd
from datetime import date
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from database.db import init_database, get_supabase, log_audit
from utils.helpers import (
    get_current_stock, get_products_df, get_warehouses_df,
    format_number, stock_status_label,
)
from utils.validators import validate_stock_entry
from utils.excel_handler import export_to_excel
from config import TRANSACTION_TYPES
from utils.auth import check_login, require_role, get_current_user, render_sidebar_user_info

init_database()

css_path = os.path.join(os.path.dirname(__file__), "..", "assets", "style.css")
if os.path.exists(css_path):
    with open(css_path) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# ── Login + RBAC ──
user = check_login()
require_role(["admin", "warehouse_manager", "data_entry", "viewer"])
render_sidebar_user_info()
can_add = user["role"] in ("admin", "warehouse_manager", "data_entry")

st.markdown("""
<div class="page-header">
    <h1>🏭 Stock Management / اسٹاک</h1>
    <p>View current stock levels, add stock transactions, and monitor inventory</p>
</div>
""", unsafe_allow_html=True)

tab_status, tab_add, tab_history = st.tabs(["📊 Stock Status", "➕ Add Transaction", "📋 Transaction History"])

# ── Stock Status ──
with tab_status:
    st.subheader("Current Stock Levels / موجودہ اسٹاک")

    # Filters
    c1, c2 = st.columns(2)
    warehouses = get_warehouses_df()
    wh_options = ["All Warehouses"] + (warehouses["name"].tolist() if not warehouses.empty else [])
    wh_sel = c1.selectbox("Filter by Warehouse", wh_options, key="stock_wh")
    wh_id = int(warehouses[warehouses["name"] == wh_sel].iloc[0]["id"]) if wh_sel != "All Warehouses" and not warehouses.empty else None

    status_filter = c2.selectbox("Filter by Status", ["All", "🔴 Critical", "🟡 Low", "🟢 Sufficient"], key="stock_status")

    stock_df = get_current_stock(warehouse_id=wh_id)

    if status_filter != "All" and not stock_df.empty:
        stock_df = stock_df[stock_df["stock_status"].str.contains(status_filter.split(" ")[1])]

    if not stock_df.empty:
        # Summary
        mc1, mc2, mc3, mc4 = st.columns(4)
        mc1.metric("Total Stock", format_number(stock_df["current_stock"].sum()))
        mc2.metric("Products Tracked", len(stock_df))
        critical = len(stock_df[stock_df["stock_status"].str.contains("Critical")])
        low = len(stock_df[stock_df["stock_status"].str.contains("Low")])
        mc3.metric("🔴 Critical", critical)
        mc4.metric("🟡 Low", low)

        # Stock Sufficiency against pending demand
        sb = get_supabase()
        pending_result = sb.table("demand_detail").select("product_id, warehouse_id, remaining").in_("status", ["Pending", "Partially Dispatched"]).execute()

        if pending_result.data:
            pending_demand = pd.DataFrame(pending_result.data)
            pending_demand["remaining"] = pd.to_numeric(pending_demand["remaining"], errors="coerce").fillna(0)
            pending_agg = pending_demand.groupby(["product_id", "warehouse_id"])["remaining"].sum().reset_index()
            pending_agg.columns = ["product_id", "warehouse_id", "pending"]

            stock_df = stock_df.merge(pending_agg, on=["product_id", "warehouse_id"], how="left")
            stock_df["pending"] = stock_df["pending"].fillna(0)
            stock_df["sufficiency"] = stock_df.apply(
                lambda r: "🟢 Sufficient" if r["current_stock"] >= r["pending"]
                else "🟡 Getting Low" if r["current_stock"] >= r["pending"] * 0.5
                else "🔴 Insufficient", axis=1
            )
        else:
            stock_df["pending"] = 0
            stock_df["sufficiency"] = "🟢 Sufficient"

        display = stock_df[[
            "product_name", "warehouse_name", "current_stock",
            "buffer_stock", "minimum_stock", "stock_status", "pending", "sufficiency"
        ]].copy()
        display.columns = [
            "Product", "Warehouse", "Current Stock",
            "Buffer", "Minimum", "Stock Status", "Pending Demand", "Sufficiency"
        ]

        def color_stock(val):
            if "Critical" in str(val) or "Insufficient" in str(val):
                return "background-color: #FFEBEE; color: #C62828; font-weight: bold"
            elif "Low" in str(val) or "Getting" in str(val):
                return "background-color: #FFF8E1; color: #E65100"
            return "background-color: #E8F5E9; color: #2E7D32"

        st.dataframe(
            display.style.map(color_stock, subset=["Stock Status", "Sufficiency"]),
            use_container_width=True, height=500
        )

        st.download_button(
            "📥 Export Stock Report",
            data=export_to_excel(display, "Stock Status"),
            file_name=f"stock_status_{date.today()}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.info("No stock data found. Add stock transactions to start tracking inventory.")

# ── Add Transaction ──
with tab_add:
    if not can_add:
        st.info("🔒 Viewers do not have permission to add stock transactions. Contact a Warehouse Manager or Admin.")
    else:
        st.subheader("Add Stock Transaction / اسٹاک ٹرانزیکشن")
        products = get_products_df()
        warehouses_list = get_warehouses_df()

        if products.empty or warehouses_list.empty:
            st.warning("Please add Products and Warehouses first.")
        else:
            with st.form("stock_form", clear_on_submit=True):
                c1, c2 = st.columns(2)
                trans_date = c1.date_input("Date / تاریخ", date.today())
                trans_type = c2.selectbox("Type / قسم", ["opening", "received", "adjustment"],
                                          format_func=lambda x: x.title())

                c3, c4 = st.columns(2)
                wh_names = warehouses_list["name"].tolist()
                wh_sel = c3.selectbox("Warehouse / گودام", wh_names, key="st_wh")
                prod_names = products["name"].tolist()
                prod_sel = c4.selectbox("Product / مصنوعات", prod_names, key="st_prod")

                c5, c6 = st.columns(2)
                quantity = c5.number_input("Quantity / مقدار", min_value=0.0, step=1.0, format="%.1f")
                remarks = c6.text_input("Remarks / ملاحظات", "")

                submitted = st.form_submit_button("✅ Add Transaction", use_container_width=True)
                if submitted:
                    wh_id = int(warehouses_list[warehouses_list["name"] == wh_sel].iloc[0]["id"])
                    prod_id = int(products[products["name"] == prod_sel].iloc[0]["id"])
                    data = {
                        "transaction_date": trans_date,
                        "warehouse_id": wh_id,
                        "product_id": prod_id,
                        "transaction_type": trans_type,
                        "quantity": quantity,
                    }
                    errors = validate_stock_entry(data)
                    if errors:
                        for e in errors:
                            st.error(e)
                    else:
                        sb = get_supabase()
                        sb.table("stock_transactions").insert({
                            "transaction_date": str(trans_date),
                            "warehouse_id": wh_id,
                            "product_id": prod_id,
                            "transaction_type": trans_type,
                            "quantity": quantity,
                            "remarks": remarks or None,
                        }).execute()
                        log_audit("stock_transactions", None, "INSERT", new_values={
                            "product": prod_sel, "warehouse": wh_sel, "type": trans_type, "qty": quantity
                        })
                        st.success(f"✅ Stock transaction recorded: {trans_type.title()} — {prod_sel}, {quantity:.0f} at {wh_sel}")

# ── Transaction History ──
with tab_history:
    st.subheader("Transaction History / ٹرانزیکشن تاریخ")

    from utils.helpers import apply_warehouse_isolation
    th_filters = apply_warehouse_isolation({})

    sb = get_supabase()
    query = sb.table("stock_transactions").select("transaction_date, warehouse_id, product_id, transaction_type, quantity, reference, remarks").eq("is_deleted", 0)
    if th_filters.get("warehouse_id"):
        query = query.eq("warehouse_id", th_filters["warehouse_id"])
    query = query.order("transaction_date", desc=True).limit(500)
    result = query.execute()

    if result.data:
        history = pd.DataFrame(result.data)

        # Get product names
        product_ids = history["product_id"].unique().tolist()
        if product_ids:
            prods = sb.table("products").select("id, name").in_("id", product_ids).execute()
            prod_map = {p["id"]: p["name"] for p in prods.data} if prods.data else {}
            history["product"] = history["product_id"].map(prod_map)

        # Get warehouse names
        wh_ids = history["warehouse_id"].unique().tolist()
        if wh_ids:
            whs = sb.table("warehouses").select("id, name").in_("id", wh_ids).execute()
            wh_map = {w["id"]: w["name"] for w in whs.data} if whs.data else {}
            history["warehouse"] = history["warehouse_id"].map(wh_map)

        display = history[["transaction_date", "product", "warehouse", "transaction_type", "quantity", "reference", "remarks"]].copy()
        display.columns = ["Date", "Product", "Warehouse", "Type", "Quantity", "Reference", "Remarks"]
        st.dataframe(display, use_container_width=True, height=500)
        st.download_button(
            "📥 Export Transactions",
            data=export_to_excel(display, "Stock Transactions"),
            file_name=f"stock_transactions_{date.today()}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.info("No transactions recorded yet.")
