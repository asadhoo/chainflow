"""
ChainFlow — Excel Import / Export Page
Upload Excel files to import data, download templates and reports.
"""
import streamlit as st
import pandas as pd
from datetime import date
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from database.db import init_database, get_supabase
from utils.validators import validate_import_dataframe
from utils.excel_handler import (
    import_products, import_warehouses, import_demand,
    import_stock, export_to_excel, generate_template,
)
from utils.helpers import (
    get_demand_df, get_current_stock, get_pending_demand,
    get_products_df, get_warehouses_df,
)
from utils.auth import check_login, require_role, get_current_user, render_sidebar_user_info

init_database()

css_path = os.path.join(os.path.dirname(__file__), "..", "assets", "style.css")
if os.path.exists(css_path):
    with open(css_path) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# ── Login + RBAC ──
user = check_login()
require_role(["admin", "warehouse_manager"])
render_sidebar_user_info()

st.markdown("""
<div class="page-header">
    <h1>📥 Import / Export</h1>
    <p>Import data from Excel files or export reports</p>
</div>
""", unsafe_allow_html=True)

tab_import, tab_export, tab_templates = st.tabs(["📤 Import Data", "📥 Export Reports", "📄 Templates"])

# ── Import ──
with tab_import:
    st.subheader("Upload Excel File / ایکسل فائل اپلوڈ کریں")

    import_type = st.selectbox("What are you importing? / آپ کیا درآمد کر رہے ہیں؟", [
        "products", "warehouses", "demand", "stock"
    ], format_func=lambda x: x.title())

    st.markdown("""
    **Import Order (important):**
    1. First import **Warehouses**
    2. Then import **Products**
    3. Then import **Demand** or **Stock**

    Products and warehouses must exist before importing demand or stock data.
    """)

    uploaded = st.file_uploader(
        f"Upload {import_type.title()} Excel file (.xlsx)",
        type=["xlsx", "xls"],
        key=f"import_{import_type}"
    )

    if uploaded:
        try:
            df = pd.read_excel(uploaded)
            st.subheader("📋 Preview / پیش نظارہ")
            st.dataframe(df.head(20), use_container_width=True)
            st.caption(f"Total rows: {len(df)}")

            # Validate
            clean_df, errors = validate_import_dataframe(df, import_type)

            if errors:
                st.subheader("⚠️ Validation Errors")
                for err in errors[:20]:
                    st.error(err)
                if len(errors) > 20:
                    st.warning(f"...and {len(errors) - 20} more errors. Fix your Excel file and try again.")
                st.warning("Invalid records will NOT be imported. Fix the errors above and re-upload.")
            else:
                st.success("✅ Data validation passed! No errors found.")

            # Import button
            if st.button(f"✅ Import {import_type.title()} ({len(df)} rows)", use_container_width=True,
                         type="primary"):
                import_funcs = {
                    "products": import_products,
                    "warehouses": import_warehouses,
                    "demand": import_demand,
                    "stock": import_stock,
                }
                count = import_funcs[import_type](clean_df)
                if count > 0:
                    st.success(f"✅ Successfully imported **{count}** {import_type} records!")
                    st.balloons()
                else:
                    st.warning("No new records were imported. They may already exist or have errors.")

        except Exception as e:
            st.error(f"Error reading Excel file: {e}")

# ── Export ──
with tab_export:
    st.subheader("Download Reports / رپورٹس ڈاؤنلوڈ کریں")

    export_options = {
        "Current Stock Report": lambda: get_current_stock(),
        "Pending Demand Report": lambda: get_pending_demand(),
        "All Demand Report": lambda: get_demand_df(),
        "Products List": lambda: get_products_df(active_only=False),
        "Warehouses List": lambda: get_warehouses_df(active_only=False),
    }

    for name, getter in export_options.items():
        col1, col2 = st.columns([3, 1])
        col1.markdown(f"**{name}**")
        df = getter()
        if not df.empty:
            col2.download_button(
                "📥 Download",
                data=export_to_excel(df, name),
                file_name=f"{name.lower().replace(' ', '_')}_{date.today()}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key=f"export_{name}",
            )
        else:
            col2.caption("No data")

    # Low Stock Report
    col1, col2 = st.columns([3, 1])
    col1.markdown("**Low Stock Report**")
    stock = get_current_stock()
    if not stock.empty:
        low = stock[stock["stock_status"].str.contains("Critical|Low")]
        if not low.empty:
            col2.download_button(
                "📥 Download",
                data=export_to_excel(low, "Low Stock"),
                file_name=f"low_stock_{date.today()}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="export_low_stock",
            )
        else:
            col2.caption("No low stock")
    else:
        col2.caption("No data")

# ── Templates ──
with tab_templates:
    st.subheader("Download Import Templates / ٹیمپلیٹ ڈاؤنلوڈ")
    st.markdown("Download blank Excel templates with the correct column headers for importing data.")

    for ttype in ["products", "warehouses", "demand", "stock"]:
        col1, col2 = st.columns([3, 1])
        col1.markdown(f"**{ttype.title()} Template**")
        col2.download_button(
            f"📄 {ttype.title()}",
            data=generate_template(ttype),
            file_name=f"{ttype}_template.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key=f"template_{ttype}",
        )
