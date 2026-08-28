"""
ChainFlow — Settings Page
Application settings, user management.
"""
import streamlit as st
import pandas as pd
from datetime import date
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from database.db import init_database, get_supabase, get_setting, set_setting
from config import APP_NAME, APP_VERSION, ROLES
from utils.auth import check_login, require_role, get_current_user, render_sidebar_user_info
import bcrypt

init_database()

css_path = os.path.join(os.path.dirname(__file__), "..", "assets", "style.css")
if os.path.exists(css_path):
    with open(css_path) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# ── Login + RBAC ──
user = check_login()
require_role(["admin"])
render_sidebar_user_info()

st.markdown(f"""
<div class="page-header">
    <h1>⚙️ Settings / ترتیبات</h1>
    <p>{APP_NAME} v{APP_VERSION} — Configuration management</p>
</div>
""", unsafe_allow_html=True)

tab_general, tab_users, tab_data, tab_about = st.tabs(
    ["🏢 General", "👥 Users", "🗃️ Data Management", "ℹ️ About"]
)

# ── General Settings ──
with tab_general:
    st.subheader("Company Settings / کمپنی کی ترتیبات")

    with st.form("settings_form"):
        company = st.text_input("Company Name / کمپنی کا نام",
                                value=get_setting("company_name", "My Pesticide Company"))
        currency = st.text_input("Currency / کرنسی", value=get_setting("currency", "PKR"))
        default_unit = st.text_input("Default Unit / ڈیفالٹ یونٹ", value=get_setting("default_unit", "KG"))

        st.markdown("---")
        st.subheader("Alert Thresholds / الرٹ حدود")
        high_pending = st.slider(
            "High Pending Demand Threshold (%) / زیرِ التوا ڈیمانڈ حد",
            min_value=10, max_value=100,
            value=int(get_setting("high_pending_threshold", "70")),
            help="Show alert when pending percentage is above this value"
        )

        language = st.selectbox("Language / زبان", ["both", "en", "ur"],
                                index=["both", "en", "ur"].index(get_setting("language", "both")),
                                format_func=lambda x: {"both": "Bilingual (English + Urdu)",
                                                       "en": "English Only", "ur": "Urdu Only"}[x])

        if st.form_submit_button("💾 Save Settings", use_container_width=True):
            set_setting("company_name", company)
            set_setting("currency", currency)
            set_setting("default_unit", default_unit)
            set_setting("high_pending_threshold", str(high_pending))
            set_setting("language", language)
            st.success("✅ Settings saved!")

# ── Users ──
with tab_users:
    st.subheader("User Management / صارف کا انتظام")

    sb = get_supabase()
    users_result = sb.table("users").select("id, username, full_name, role, is_active, warehouse_id").order("username").execute()

    if users_result.data:
        users_df = pd.DataFrame(users_result.data)

        # Get warehouse names for users
        wh_ids = [u["warehouse_id"] for u in users_result.data if u.get("warehouse_id")]
        wh_map = {}
        if wh_ids:
            whs = sb.table("warehouses").select("id, name").in_("id", list(set(wh_ids))).execute()
            wh_map = {w["id"]: w["name"] for w in whs.data} if whs.data else {}

        users_df["warehouse_name"] = users_df["warehouse_id"].map(wh_map)

        display_users = users_df[["username", "full_name", "role", "warehouse_name", "is_active"]].copy()
        display_users.columns = ["Username", "Full Name", "Role", "Warehouse", "Active"]
        display_users["Role"] = display_users["Role"].map(lambda r: ROLES.get(r, r))
        display_users["Warehouse"] = display_users["Warehouse"].fillna("— (All)")
        display_users["Active"] = display_users["Active"].map({1: "✅ Yes", 0: "❌ No"})
        st.dataframe(display_users, use_container_width=True, height=300)
    else:
        users_df = pd.DataFrame()
        st.info("No users found.")

    st.markdown("---")
    st.subheader("➕ Add New User / نیا صارف شامل کریں")

    warehouses_result = sb.table("warehouses").select("id, name").eq("is_deleted", 0).order("name").execute()
    warehouses_all = pd.DataFrame(warehouses_result.data) if warehouses_result.data else pd.DataFrame()

    with st.form("add_user_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        new_username = c1.text_input("Username *")
        new_full_name = c2.text_input("Full Name *")

        c3, c4 = st.columns(2)
        new_password = c3.text_input("Password *", type="password")
        role_keys = list(ROLES.keys())
        new_role = c4.selectbox("Role *", role_keys, format_func=lambda r: ROLES.get(r, r))

        wh_names = ["— None (Admin / All Warehouses) —"] + warehouses_all["name"].tolist() if not warehouses_all.empty else ["— None (Admin / All Warehouses) —"]
        new_wh_sel = st.selectbox("Warehouse (required for non-admin roles)", wh_names)

        if st.form_submit_button("✅ Add User", use_container_width=True):
            errs = []
            if not new_username.strip():
                errs.append("Username is required.")
            if not new_full_name.strip():
                errs.append("Full name is required.")
            if not new_password:
                errs.append("Password is required.")
            wh_id = None
            if new_wh_sel != "— None (Admin / All Warehouses) —" and not warehouses_all.empty:
                wh_id = int(warehouses_all[warehouses_all["name"] == new_wh_sel].iloc[0]["id"])
            if new_role != "admin" and not wh_id:
                errs.append("A warehouse must be assigned for non-admin roles.")

            if errs:
                for e in errs:
                    st.error(e)
            else:
                existing = sb.table("users").select("id").eq("username", new_username.strip()).execute()
                if existing.data:
                    st.error(f"Username '{new_username}' already exists.")
                else:
                    pw_hash = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
                    sb.table("users").insert({
                        "username": new_username.strip(),
                        "password_hash": pw_hash,
                        "full_name": new_full_name.strip(),
                        "role": new_role,
                        "warehouse_id": wh_id,
                    }).execute()
                    st.success(f"✅ User **{new_username}** created.")
                    st.rerun()

    st.markdown("---")
    st.subheader("✏️ Edit User / صارف میں ترمیم")

    if not users_df.empty:
        edit_usernames = users_df["username"].tolist()
        sel_user = st.selectbox("Select User", edit_usernames, key="edit_user_sel")
        if sel_user:
            urow = users_df[users_df["username"] == sel_user].iloc[0]
            with st.form("edit_user_form"):
                c1, c2 = st.columns(2)
                role_keys = list(ROLES.keys())
                edit_role = c1.selectbox(
                    "Role", role_keys,
                    index=role_keys.index(urow["role"]) if urow["role"] in role_keys else 0,
                    format_func=lambda r: ROLES.get(r, r),
                )
                wh_names_edit = ["— None (Admin / All Warehouses) —"] + warehouses_all["name"].tolist() if not warehouses_all.empty else ["— None (Admin / All Warehouses) —"]
                cur_wh_idx = 0
                if pd.notna(urow.get("warehouse_name")) and urow.get("warehouse_name") in wh_names_edit:
                    cur_wh_idx = wh_names_edit.index(urow["warehouse_name"])
                edit_wh_sel = c2.selectbox("Warehouse", wh_names_edit, index=cur_wh_idx)

                edit_active = st.checkbox("Active", value=bool(urow["is_active"]))
                new_pw = st.text_input("Reset Password (leave blank to keep current)", type="password")

                if st.form_submit_button("💾 Save Changes", use_container_width=True):
                    edit_wh_id = None
                    if edit_wh_sel != "— None (Admin / All Warehouses) —" and not warehouses_all.empty:
                        edit_wh_id = int(warehouses_all[warehouses_all["name"] == edit_wh_sel].iloc[0]["id"])

                    if edit_role != "admin" and not edit_wh_id:
                        st.error("A warehouse must be assigned for non-admin roles.")
                    else:
                        update_data = {
                            "role": edit_role,
                            "warehouse_id": edit_wh_id,
                            "is_active": 1 if edit_active else 0,
                        }
                        if new_pw:
                            update_data["password_hash"] = bcrypt.hashpw(new_pw.encode(), bcrypt.gensalt()).decode()

                        sb.table("users").update(update_data).eq("id", int(urow["id"])).execute()
                        st.success(f"✅ User **{sel_user}** updated.")
                        st.rerun()

# ── Data Management ──
with tab_data:
    st.subheader("Database Statistics / ڈیٹا بیس اعدادوشمار")
    sb = get_supabase()

    tables = {
        "Products": "products",
        "Warehouses": "warehouses",
        "Categories": "product_categories",
        "Demand Records": "demand",
        "Dispatch Records": "dispatch",
        "Stock Transactions": "stock_transactions",
        "Audit Log": "audit_log",
    }

    for label, table in tables.items():
        result = sb.table(table).select("*", count="exact").limit(0).execute()
        st.metric(label, result.count if result.count is not None else 0)

    st.markdown("---")
    st.subheader("⚠️ Danger Zone")
    st.warning("These actions cannot be undone. Be careful!")

    if st.checkbox("I understand this will delete data permanently"):
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🗑️ Clear Audit Log", use_container_width=True):
                sb.table("audit_log").delete().neq("id", 0).execute()
                st.success("Audit log cleared.")

        with col2:
            if st.button("🗑️ Clear All Transaction Data", use_container_width=True):
                sb.table("dispatch").delete().neq("id", 0).execute()
                sb.table("stock_transactions").delete().neq("id", 0).execute()
                sb.table("demand").delete().neq("id", 0).execute()
                st.success("All transaction data cleared. Master data (products, warehouses) preserved.")

    # ── Recycle Bin ──
    st.markdown("---")
    st.subheader("🗑️ Recycle Bin / ری سائیکل بن")
    st.caption("Soft-deleted records can be restored from here. Nothing here is permanently removed.")

    recycle_tables = {
        "Demand": ("demand", ["reference", "demand_date", "quantity", "status"]),
        "Dispatch": ("dispatch", ["dispatch_date", "quantity", "remarks"]),
        "Stock Transactions": ("stock_transactions", ["transaction_date", "transaction_type", "quantity", "remarks"]),
        "Products": ("products", ["code", "name"]),
        "Warehouses": ("warehouses", ["code", "name", "location"]),
    }

    recycle_choice = st.selectbox("Select table to view deleted records", list(recycle_tables.keys()))
    table_name, cols = recycle_tables[recycle_choice]

    col_str = ", ".join(["id"] + cols)
    deleted_result = sb.table(table_name).select(col_str).eq("is_deleted", 1).execute()
    deleted_df = pd.DataFrame(deleted_result.data) if deleted_result.data else pd.DataFrame()

    if deleted_df.empty:
        st.info(f"No deleted {recycle_choice.lower()} records found.")
    else:
        st.dataframe(deleted_df, use_container_width=True, height=250)
        restore_id = st.selectbox("Select record ID to restore", deleted_df["id"].tolist(), key="restore_id_sel")
        if st.button("♻️ Restore Selected Record", use_container_width=True):
            sb.table(table_name).update({"is_deleted": 0}).eq("id", int(restore_id)).execute()
            st.success(f"✅ Record restored from {recycle_choice} recycle bin.")
            st.rerun()

# ── About ──
with tab_about:
    st.subheader(f"About {APP_NAME}")
    st.markdown(f"""
    **{APP_NAME}** v{APP_VERSION}

    A professional Supply Chain Management Dashboard built for pesticide companies in Pakistan.

    **Features:**
    - Dashboard with real-time KPIs and alerts
    - Demand and dispatch tracking
    - Inventory/stock management with status indicators
    - Excel import and export
    - Multi-warehouse support
    - Bilingual interface (English + Urdu)
    - Year-on-year comparison
    - Comprehensive reports

    **Technology:**
    - Python + Streamlit
    - Supabase (PostgreSQL)
    - Pandas + Plotly

    **Built with ❤️ for Pakistani Agriculture**
    """)
