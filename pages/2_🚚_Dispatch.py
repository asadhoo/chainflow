"""
ChainFlow — Dispatch Management Page
Record dispatches against demand, track delivery progress.
"""
import streamlit as st
import pandas as pd
from datetime import date
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from database.db import init_database, get_supabase, log_audit
from utils.helpers import get_demand_df, format_number
from utils.validators import validate_dispatch_entry
from utils.excel_handler import export_to_excel
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
    <h1>🚚 Dispatch Management / ترسیل</h1>
    <p>Record dispatches against demand orders and track delivery progress</p>
</div>
""", unsafe_allow_html=True)

tab_add, tab_view = st.tabs(["➕ Add Dispatch", "📋 View Dispatches"])

# ── Add Dispatch ──
with tab_add:
    if not can_add:
        st.info("🔒 Viewers do not have permission to record dispatches. Contact a Warehouse Manager or Admin.")
    else:
        st.subheader("Record Dispatch / ترسیل درج کریں")

        # Load pending demand
        demand_df = get_demand_df()
        pending = demand_df[demand_df["status"].isin(["Pending", "Partially Dispatched"])] if not demand_df.empty else pd.DataFrame()

        if pending.empty:
            st.info("No pending demand found. All demand has been fulfilled or no demand exists.")
        else:
            # Show pending demand summary
            st.markdown("**Pending Demand Orders:**")
            summary = pending[["reference", "product_name", "warehouse_name", "quantity", "delivered", "remaining"]].copy()
            summary.columns = ["Reference", "Product", "Warehouse", "Demand", "Delivered", "Remaining"]
            st.dataframe(summary, use_container_width=True, height=200)

            with st.form("dispatch_form", clear_on_submit=True):
                c1, c2 = st.columns(2)
                dispatch_date = c1.date_input("Dispatch Date / ترسیل کی تاریخ", date.today())

                refs = pending["reference"].tolist()
                sel_ref = c2.selectbox("Demand Reference / ڈیمانڈ حوالہ", refs)

                # Show selected demand info
                if sel_ref:
                    sel_row = pending[pending["reference"] == sel_ref].iloc[0]
                    st.info(
                        f"**{sel_row['product_name']}** — {sel_row['warehouse_name']} | "
                        f"Demand: {sel_row['quantity']:.0f} | Delivered: {sel_row['delivered']:.0f} | "
                        f"Remaining: **{sel_row['remaining']:.0f}**"
                    )
                    max_qty = float(sel_row["remaining"])
                else:
                    max_qty = 0.0

                c3, c4 = st.columns(2)
                quantity = c3.number_input("Dispatch Quantity / مقدار", min_value=0.0, max_value=max_qty, step=1.0, format="%.1f")
                remarks = c4.text_input("Remarks / ملاحظات", "")

                submitted = st.form_submit_button("✅ Record Dispatch", use_container_width=True)

                if submitted and sel_ref:
                    sel_row = pending[pending["reference"] == sel_ref].iloc[0]
                    data = {
                        "dispatch_date": dispatch_date,
                        "demand_id": int(sel_row["id"]),
                        "quantity": quantity,
                    }
                    errors = validate_dispatch_entry(data)
                    if errors:
                        for e in errors:
                            st.error(e)
                    else:
                        sb = get_supabase()
                        # Insert dispatch
                        sb.table("dispatch").insert({
                            "dispatch_date": str(dispatch_date),
                            "demand_id": int(sel_row["id"]),
                            "warehouse_id": int(sel_row["warehouse_id"]),
                            "product_id": int(sel_row["product_id"]),
                            "quantity": quantity,
                            "remarks": remarks or None,
                        }).execute()

                        # Record stock transaction (dispatched from warehouse)
                        sb.table("stock_transactions").insert({
                            "transaction_date": str(dispatch_date),
                            "warehouse_id": int(sel_row["warehouse_id"]),
                            "product_id": int(sel_row["product_id"]),
                            "transaction_type": "dispatched",
                            "quantity": quantity,
                            "reference": sel_ref,
                            "remarks": f"Dispatch against {sel_ref}",
                        }).execute()

                        # Update demand status
                        new_delivered = sel_row["delivered"] + quantity
                        new_status = "Fully Dispatched" if new_delivered >= sel_row["quantity"] else "Partially Dispatched"
                        sb.table("demand").update({
                            "status": new_status,
                        }).eq("id", int(sel_row["id"])).execute()

                        log_audit("dispatch", None, "INSERT", new_values={
                            "demand_ref": sel_ref, "qty": quantity, "date": str(dispatch_date)
                        })
                        st.success(f"✅ Dispatched **{quantity:.0f}** against {sel_ref}. Status: **{new_status}**")
                        st.rerun()

# ── View Dispatches ──
with tab_view:
    st.subheader("Dispatch History / ترسیل کی تاریخ")

    from utils.helpers import apply_warehouse_isolation
    dv_filters = apply_warehouse_isolation({})

    sb = get_supabase()
    # Query dispatch with joins via a view or manual query
    # Since we don't have a dispatch_detail view, we query and join in Python
    query = sb.table("dispatch").select("id, dispatch_date, demand_id, warehouse_id, product_id, quantity, remarks, created_at").eq("is_deleted", 0)
    if dv_filters.get("warehouse_id"):
        query = query.eq("warehouse_id", dv_filters["warehouse_id"])
    query = query.order("dispatch_date", desc=True)
    dispatch_result = query.execute()

    if dispatch_result.data:
        dispatch_df = pd.DataFrame(dispatch_result.data)

        # Get demand references
        demand_ids = dispatch_df["demand_id"].unique().tolist()
        if demand_ids:
            demands = sb.table("demand").select("id, reference").in_("id", demand_ids).execute()
            demand_map = {d["id"]: d["reference"] for d in demands.data} if demands.data else {}
            dispatch_df["demand_ref"] = dispatch_df["demand_id"].map(demand_map)

        # Get product names
        product_ids = dispatch_df["product_id"].unique().tolist()
        if product_ids:
            products = sb.table("products").select("id, name").in_("id", product_ids).execute()
            prod_map = {p["id"]: p["name"] for p in products.data} if products.data else {}
            dispatch_df["product_name"] = dispatch_df["product_id"].map(prod_map)

        # Get warehouse names
        wh_ids = dispatch_df["warehouse_id"].unique().tolist()
        if wh_ids:
            whs = sb.table("warehouses").select("id, name").in_("id", wh_ids).execute()
            wh_map = {w["id"]: w["name"] for w in whs.data} if whs.data else {}
            dispatch_df["warehouse_name"] = dispatch_df["warehouse_id"].map(wh_map)

        mc1, mc2, mc3 = st.columns(3)
        mc1.metric("Total Dispatches", len(dispatch_df))
        mc2.metric("Total Quantity", format_number(dispatch_df["quantity"].sum()))
        mc3.metric("Latest Dispatch", dispatch_df["dispatch_date"].iloc[0])

        display = dispatch_df[["dispatch_date", "demand_ref", "product_name", "warehouse_name", "quantity", "remarks"]].copy()
        display.columns = ["Date", "Demand Ref", "Product", "Warehouse", "Quantity", "Remarks"]
        st.dataframe(display, use_container_width=True, height=500)

        st.download_button(
            "📥 Export to Excel",
            data=export_to_excel(display, "Dispatches"),
            file_name=f"dispatch_report_{date.today()}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.info("No dispatch records yet. Use the **Add Dispatch** tab to record deliveries.")
