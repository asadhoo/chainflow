"""
ChainFlow — Product Management Page
Add, edit, and manage products and categories.
"""
import streamlit as st
import pandas as pd
from datetime import date
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from database.db import init_database, get_supabase, log_audit
from utils.helpers import get_products_df, get_categories_df
from utils.validators import validate_product_entry
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
    <h1>🧪 Products / مصنوعات</h1>
    <p>Manage product master data, categories, and stock thresholds</p>
</div>
""", unsafe_allow_html=True)

tab_list, tab_add, tab_cat = st.tabs(["📋 Product List", "➕ Add Product", "🏷️ Categories"])

# ── Product List ──
with tab_list:
    products = get_products_df(active_only=False)
    if not products.empty:
        search = st.text_input("🔍 Search products...", key="prod_search")
        if search:
            s = search.lower()
            products = products[
                products["name"].str.lower().str.contains(s, na=False) |
                products["code"].str.lower().str.contains(s, na=False)
            ]

        mc1, mc2, mc3 = st.columns(3)
        mc1.metric("Total Products", len(products))
        mc2.metric("Active", len(products[products["is_active"] == 1]))
        mc3.metric("Inactive", len(products[products["is_active"] == 0]))

        display = products[[
            "code", "name", "category_name", "pack_size", "unit",
            "minimum_stock", "buffer_stock", "is_active"
        ]].copy()
        display.columns = ["Code", "Name", "Category", "Pack Size", "Unit", "Min Stock", "Buffer Stock", "Active"]
        display["Active"] = display["Active"].map({1: "✅ Yes", 0: "❌ No"})
        st.dataframe(display, use_container_width=True, height=400)

        # Edit product
        if not can_edit:
            st.info("🔒 Only Warehouse Managers and Admins can edit products.")
        else:
          st.markdown("---")
          st.subheader("✏️ Edit Product")
          prod_names = products["name"].tolist()
          sel_prod = st.selectbox("Select Product to Edit", prod_names)
          if sel_prod:
            row = products[products["name"] == sel_prod].iloc[0]
            categories = get_categories_df(active_only=False)
            cat_names = categories["name"].tolist() if not categories.empty else []

            with st.form("edit_product_form"):
                c1, c2 = st.columns(2)
                code = c1.text_input("Code", value=row["code"])
                name = c2.text_input("Name", value=row["name"])

                c3, c4 = st.columns(2)
                cat_idx = cat_names.index(row["category_name"]) if row.get("category_name") in cat_names else 0
                category = c3.selectbox("Category", cat_names, index=cat_idx) if cat_names else c3.text_input("Category", "")
                pack_size = c4.text_input("Pack Size", value=row.get("pack_size", "") or "")

                c5, c6, c7 = st.columns(3)
                unit = c5.text_input("Unit", value=row.get("unit", "KG") or "KG")
                min_stock = c6.number_input("Minimum Stock", value=float(row.get("minimum_stock", 0) or 0))
                buffer_stock = c7.number_input("Buffer Stock", value=float(row.get("buffer_stock", 0) or 0))

                is_active = st.checkbox("Active", value=bool(row["is_active"]))

                if st.form_submit_button("💾 Save Changes", use_container_width=True):
                    cat_id = None
                    if category and not categories.empty:
                        cat_row = categories[categories["name"] == category]
                        if not cat_row.empty:
                            cat_id = int(cat_row.iloc[0]["id"])

                    errors = validate_product_entry({"code": code, "name": name, "id": int(row["id"])})
                    if errors:
                        for e in errors:
                            st.error(e)
                    else:
                        sb = get_supabase()
                        sb.table("products").update({
                            "code": code,
                            "name": name,
                            "category_id": cat_id,
                            "pack_size": pack_size or None,
                            "unit": unit,
                            "minimum_stock": min_stock,
                            "buffer_stock": buffer_stock,
                            "is_active": 1 if is_active else 0,
                        }).eq("id", int(row["id"])).execute()
                        log_audit("products", int(row["id"]), "UPDATE")
                        st.success(f"✅ Product **{name}** updated.")
                        st.rerun()
    else:
        st.info("No products found. Use the **Add Product** tab.")

# ── Add Product ──
with tab_add:
  if not can_edit:
    st.info("🔒 Only Warehouse Managers and Admins can add products.")
  else:
    st.subheader("Add New Product / نئی مصنوعات")
    categories = get_categories_df()
    cat_names = categories["name"].tolist() if not categories.empty else ["Other"]

    with st.form("add_product_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        code = c1.text_input("Product Code *", placeholder="e.g., INS-001")
        name = c2.text_input("Product Name *", placeholder="e.g., Alpha Cypermethrin")

        c3, c4, c5 = st.columns(3)
        category = c3.selectbox("Category / زمرہ", cat_names)
        pack_size = c4.text_input("Pack Size", placeholder="e.g., 250 ML, 1 Litre")
        packing_type = c5.text_input("Packing Type", placeholder="e.g., Bottle, Bag")

        c6, c7, c8, c9 = st.columns(4)
        unit = c6.text_input("Unit", value="KG")
        min_stock = c7.number_input("Minimum Stock", min_value=0.0, value=0.0)
        buffer_stock = c8.number_input("Buffer Stock", min_value=0.0, value=0.0)
        opening_stock = c9.number_input("Opening Stock", min_value=0.0, value=0.0)

        if st.form_submit_button("✅ Add Product", use_container_width=True):
            errors = validate_product_entry({"code": code, "name": name, "id": 0})
            if errors:
                for e in errors:
                    st.error(e)
            else:
                sb = get_supabase()
                cat_id = None
                if not categories.empty:
                    cat_row = categories[categories["name"] == category]
                    if not cat_row.empty:
                        cat_id = int(cat_row.iloc[0]["id"])

                result = sb.table("products").insert({
                    "code": code.strip(),
                    "name": name.strip(),
                    "category_id": cat_id,
                    "pack_size": pack_size or None,
                    "packing_type": packing_type or None,
                    "unit": unit,
                    "minimum_stock": min_stock,
                    "buffer_stock": buffer_stock,
                    "opening_stock": opening_stock,
                }).execute()
                prod_id = result.data[0]["id"]

                # If opening stock > 0, create stock transaction
                if opening_stock > 0:
                    wh_result = sb.table("warehouses").select("id").eq("is_active", 1).limit(1).execute()
                    if wh_result.data:
                        sb.table("stock_transactions").insert({
                            "transaction_date": str(date.today()),
                            "warehouse_id": wh_result.data[0]["id"],
                            "product_id": prod_id,
                            "transaction_type": "opening",
                            "quantity": opening_stock,
                            "remarks": "Opening stock entry",
                        }).execute()

                log_audit("products", prod_id, "INSERT", new_values={"code": code, "name": name})
                st.success(f"✅ Product **{name}** ({code}) added successfully!")

# ── Categories ──
with tab_cat:
    st.subheader("Product Categories / مصنوعات کے زمرے")
    categories = get_categories_df(active_only=False)

    if not categories.empty:
        display_cats = categories[["name", "name_urdu", "is_active"]].copy()
        display_cats.columns = ["Name", "Urdu Name", "Active"]
        display_cats["Active"] = display_cats["Active"].map({1: "✅", 0: "❌"})
        st.dataframe(display_cats, use_container_width=True)

    if can_edit:
      st.markdown("---")
      with st.form("add_category_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        cat_name = c1.text_input("Category Name *")
        cat_urdu = c2.text_input("Urdu Name")
        if st.form_submit_button("➕ Add Category"):
            if cat_name.strip():
                sb = get_supabase()
                try:
                    sb.table("product_categories").insert({
                        "name": cat_name.strip(),
                        "name_urdu": cat_urdu.strip() or None,
                    }).execute()
                    st.success(f"✅ Category **{cat_name}** added.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Category may already exist: {e}")
            else:
                st.error("Category name is required.")
