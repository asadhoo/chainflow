"""
ChainFlow — Demand Management Page
Add, view, edit, and manage demand records.
"""
import streamlit as st
import pandas as pd
from datetime import date, datetime
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from database.db import init_database, get_supabase, log_audit
from utils.helpers import (
    get_demand_df, get_products_df, get_warehouses_df, get_categories_df,
    generate_reference, format_number, apply_sidebar_filters,
)
from utils.validators import validate_demand_entry
from utils.excel_handler import export_to_excel
from config import get_label, DISPATCH_STATUS
from utils.auth import check_login, require_role, get_current_user, render_sidebar_user_info

init_database()

# ── Load CSS ──
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
    <h1>📦 Demand Management / ڈیمانڈ</h1>
    <p>Add new demand, view and manage existing demand records</p>
</div>
""", unsafe_allow_html=True)

# ── Sidebar Filters ──
filters = apply_sidebar_filters()

# ── Tabs ──
tab_add, tab_view = st.tabs(["➕ Add Demand", "📋 View Demand"])

# ── Add Demand ──
with tab_add:
    if not can_add:
        st.info("🔒 Viewers do not have permission to add demand records. Contact a Warehouse Manager or Admin.")
    else:
        st.subheader("Add New Demand / نئی ڈیمانڈ")
        products = get_products_df()
        warehouses = get_warehouses_df()
        categories = get_categories_df()

        if products.empty or warehouses.empty:
            st.warning("⚠️ Please add Products and Warehouses first before creating demand.")
        else:
            with st.form("demand_form", clear_on_submit=True):
                c1, c2 = st.columns(2)
                demand_date = c1.date_input("Demand Date / ڈیمانڈ کی تاریخ", date.today())
                required_date = c2.date_input("Required Date / مطلوبہ تاریخ", date.today())

                c3, c4 = st.columns(2)
                wh_names = warehouses["name"].tolist()
                wh_sel = c3.selectbox("Warehouse / گودام", wh_names)
                wh_id = int(warehouses[warehouses["name"] == wh_sel].iloc[0]["id"])

                prod_names = products["name"].tolist()
                prod_sel = c4.selectbox("Product / مصنوعات", prod_names)
                prod_row = products[products["name"] == prod_sel].iloc[0]
                prod_id = int(prod_row["id"])
                cat_id = int(prod_row["category_id"]) if pd.notna(prod_row.get("category_id")) else None

                c5, c6 = st.columns(2)
                quantity = c5.number_input("Quantity / مقدار", min_value=0.0, step=1.0, format="%.1f")
                remarks = c6.text_input("Remarks / ملاحظات", "")

                submitted = st.form_submit_button("✅ Add Demand", use_container_width=True)

                if submitted:
                    data = {
                        "demand_date": demand_date,
                        "required_date": required_date,
                        "warehouse_id": wh_id,
                        "product_id": prod_id,
                        "quantity": quantity,
                    }
                    errors = validate_demand_entry(data)
                    if errors:
                        for e in errors:
                            st.error(e)
                    else:
                        sb = get_supabase()
                        ref = generate_reference("DEM")
                        sb.table("demand").insert({
                            "reference": ref,
                            "demand_date": str(demand_date),
                            "required_date": str(required_date),
                            "warehouse_id": wh_id,
                            "product_id": prod_id,
                            "category_id": cat_id,
                            "quantity": quantity,
                            "remarks": remarks or None,
                        }).execute()
                        log_audit("demand", None, "INSERT", new_values={
                            "reference": ref, "product": prod_sel, "warehouse": wh_sel, "qty": quantity
                        })
                        st.success(f"✅ Demand created: **{ref}** — {prod_sel}, {quantity} from {wh_sel}")

# ── View Demand ──
with tab_view:
    st.subheader("Demand Records / ڈیمانڈ ریکارڈز")

    # Search
    search = st.text_input("🔍 Search by product, warehouse, or reference...")

    demand_df = get_demand_df(filters)

    if search and not demand_df.empty:
        s = search.lower()
        demand_df = demand_df[
            demand_df["product_name"].str.lower().str.contains(s, na=False) |
            demand_df["warehouse_name"].str.lower().str.contains(s, na=False) |
            demand_df["reference"].str.lower().str.contains(s, na=False) |
            demand_df["product_code"].str.lower().str.contains(s, na=False)
        ]

    if not demand_df.empty:
        # Summary metrics
        mc1, mc2, mc3, mc4 = st.columns(4)
        mc1.metric("Total Records", len(demand_df))
        mc2.metric("Total Demand", format_number(demand_df["quantity"].sum()))
        mc3.metric("Total Delivered", format_number(demand_df["delivered"].sum()))
        mc4.metric("Total Pending", format_number(demand_df["remaining"].sum()))

        # Display table
        display = demand_df[[
            "reference", "demand_date", "product_name", "warehouse_name",
            "quantity", "delivered", "remaining", "delivery_pct", "status", "remarks"
        ]].copy()
        display.columns = [
            "Reference", "Date", "Product", "Warehouse",
            "Demand", "Delivered", "Remaining", "% Done", "Status", "Remarks"
        ]

        def style_status(val):
            colors = {
                "Fully Dispatched": "background-color: #E8F5E9; color: #2E7D32",
                "Partially Dispatched": "background-color: #FFF8E1; color: #E65100",
                "Cancelled": "background-color: #F5F5F5; color: #757575",
                "Pending": "background-color: #FFEBEE; color: #C62828",
            }
            return colors.get(val, "")

        st.dataframe(
            display.style.map(style_status, subset=["Status"]),
            use_container_width=True, height=500
        )

        # Export button
        st.download_button(
            "📥 Export to Excel",
            data=export_to_excel(display, "Demand"),
            file_name=f"demand_report_{date.today()}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        # ── Edit / Cancel Demand ──
        if can_add:
            st.markdown("---")
            st.subheader("✏️ Edit Demand Status")
            refs = demand_df["reference"].tolist()
            sel_ref = st.selectbox("Select Demand Reference", refs)
            if sel_ref:
                row = demand_df[demand_df["reference"] == sel_ref].iloc[0]
                new_status = st.selectbox("Change Status", DISPATCH_STATUS,
                                          index=DISPATCH_STATUS.index(row["status"]) if row["status"] in DISPATCH_STATUS else 0)
                new_remarks = st.text_input("Update Remarks", value=row.get("remarks", "") or "")

                if st.button("💾 Update Demand", use_container_width=True):
                    sb = get_supabase()
                    sb.table("demand").update({
                        "status": new_status,
                        "remarks": new_remarks or None,
                    }).eq("reference", sel_ref).execute()
                    log_audit("demand", row["id"], "UPDATE", old_values={"status": row["status"]},
                              new_values={"status": new_status})
                    st.success(f"✅ Demand {sel_ref} updated to **{new_status}**")
                    st.rerun()
    else:
        st.info("No demand records found. Use the **Add Demand** tab or adjust your filters.")
