"""
ChainFlow — Warehouse Management Page
"""
import streamlit as st
import pandas as pd
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from database.db import init_database, get_supabase, log_audit
from utils.helpers import get_warehouses_df
from utils.validators import validate_warehouse_entry
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
can_edit = user["role"] in ("admin", "warehouse_manager")

st.markdown("""
<div class="page-header">
    <h1>🏢 Warehouses / گودام</h1>
    <p>Manage warehouse locations across Pakistan</p>
</div>
""", unsafe_allow_html=True)

tab_list, tab_add = st.tabs(["📋 Warehouse List", "➕ Add Warehouse"])

# ── Warehouse List ──
with tab_list:
    warehouses = get_warehouses_df(active_only=False)
    if not warehouses.empty:
        mc1, mc2 = st.columns(2)
        mc1.metric("Total Warehouses", len(warehouses))
        mc2.metric("Active", len(warehouses[warehouses["is_active"] == 1]))

        display = warehouses[["code", "name", "location", "is_active"]].copy()
        display.columns = ["Code", "Name", "Location", "Active"]
        display["Active"] = display["Active"].map({1: "✅ Yes", 0: "❌ No"})
        st.dataframe(display, use_container_width=True)

        # Edit
        if not can_edit:
            st.info("🔒 Only Warehouse Managers and Admins can edit warehouses.")
        else:
          st.markdown("---")
          st.subheader("✏️ Edit Warehouse")
          wh_names = warehouses["name"].tolist()
          sel_wh = st.selectbox("Select Warehouse", wh_names)
          if sel_wh:
            row = warehouses[warehouses["name"] == sel_wh].iloc[0]
            with st.form("edit_wh_form"):
                c1, c2 = st.columns(2)
                code = c1.text_input("Code", value=row["code"])
                name = c2.text_input("Name", value=row["name"])
                c3, c4 = st.columns(2)
                location = c3.text_input("Location", value=row.get("location", "") or "")
                is_active = c4.checkbox("Active", value=bool(row["is_active"]))

                if st.form_submit_button("💾 Save Changes", use_container_width=True):
                    errors = validate_warehouse_entry({"code": code, "name": name, "id": int(row["id"])})
                    if errors:
                        for e in errors:
                            st.error(e)
                    else:
                        sb = get_supabase()
                        sb.table("warehouses").update({
                            "code": code,
                            "name": name,
                            "location": location or None,
                            "is_active": 1 if is_active else 0,
                        }).eq("id", int(row["id"])).execute()
                        log_audit("warehouses", int(row["id"]), "UPDATE")
                        st.success(f"✅ Warehouse **{name}** updated.")
                        st.rerun()
    else:
        st.info("No warehouses found. Add your first warehouse below.")

# ── Add Warehouse ──
with tab_add:
  if not can_edit:
    st.info("🔒 Only Warehouse Managers and Admins can add warehouses.")
  else:
    st.subheader("Add New Warehouse / نیا گودام")
    with st.form("add_wh_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        code = c1.text_input("Warehouse Code *", placeholder="e.g., WH-MLT")
        name = c2.text_input("Warehouse Name *", placeholder="e.g., Multan")
        location = st.text_input("Location / مقام", placeholder="e.g., Industrial Area, Multan")

        if st.form_submit_button("✅ Add Warehouse", use_container_width=True):
            errors = validate_warehouse_entry({"code": code, "name": name, "id": 0})
            if errors:
                for e in errors:
                    st.error(e)
            else:
                sb = get_supabase()
                result = sb.table("warehouses").insert({
                    "code": code.strip(),
                    "name": name.strip(),
                    "location": location.strip() or None,
                }).execute()
                wh_id = result.data[0]["id"]
                log_audit("warehouses", wh_id, "INSERT", new_values={"code": code, "name": name})
                st.success(f"✅ Warehouse **{name}** ({code}) added!")
                st.rerun()

    # Quick-add common Pakistan warehouses
    st.markdown("---")
    st.subheader("⚡ Quick Add Common Warehouses")
    common_wh = {
        "WH-MLT": ("Multan", "South Punjab"),
        "WH-DGK": ("DG Khan", "South Punjab"),
        "WH-BWP": ("Bahawalpur", "South Punjab"),
        "WH-KHN": ("Khanewal", "South Punjab"),
        "WH-MZG": ("Muzaffargarh", "South Punjab"),
        "WH-LHR": ("Lahore", "Central Punjab"),
        "WH-FSD": ("Faisalabad", "Central Punjab"),
        "WH-RWP": ("Rawalpindi", "North Punjab"),
    }

    existing = get_warehouses_df(active_only=False)
    existing_codes = set(existing["code"].tolist()) if not existing.empty else set()

    available = {k: v for k, v in common_wh.items() if k not in existing_codes}
    if available:
        selected = st.multiselect(
            "Select warehouses to add",
            [f"{v[0]} ({k})" for k, v in available.items()]
        )
        if st.button("➕ Add Selected Warehouses") and selected:
            sb = get_supabase()
            count = 0
            for item in selected:
                name_part = item.split(" (")[0]
                code_part = item.split("(")[1].rstrip(")")
                loc = available.get(code_part, ("", ""))[1]
                try:
                    sb.table("warehouses").insert({
                        "code": code_part,
                        "name": name_part,
                        "location": loc,
                    }).execute()
                    count += 1
                except Exception:
                    pass
            st.success(f"✅ Added {count} warehouses!")
            st.rerun()
    else:
        st.success("All common warehouses have been added!")
