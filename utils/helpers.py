"""
ChainFlow — Common helper functions used across all pages.
"""
import pandas as pd
import streamlit as st
from datetime import datetime, date
from database.db import get_supabase, get_setting


def apply_warehouse_isolation(filters):
    """Auto-inject warehouse_id for non-admin users."""
    try:
        from utils.auth import get_user_warehouse_id
        wh_id = get_user_warehouse_id()
        if wh_id and not filters.get("warehouse_id"):
            filters["warehouse_id"] = wh_id
    except (ImportError, Exception):
        pass
    return filters


def generate_reference(prefix="DEM"):
    """Generate a unique reference like DEM-20260825-001."""
    sb = get_supabase()
    today = date.today().strftime("%Y%m%d")
    pattern = f"{prefix}-{today}-"

    result = sb.table("demand").select("reference").like("reference", f"{pattern}%").order("reference", desc=True).limit(1).execute()

    if result.data:
        last_num = int(result.data[0]["reference"].split("-")[-1])
        return f"{pattern}{last_num + 1:03d}"
    return f"{pattern}001"


def get_products_df(active_only=True):
    """Load products as DataFrame using products_detail view."""
    sb = get_supabase()
    query = sb.table("products_detail").select("*")
    if active_only:
        query = query.eq("is_active", 1)
    query = query.order("name")
    result = query.execute()
    return pd.DataFrame(result.data) if result.data else pd.DataFrame()


def get_warehouses_df(active_only=True):
    """Load warehouses as DataFrame. Non-admin users only see their assigned warehouse."""
    sb = get_supabase()
    query = sb.table("warehouses").select("*").eq("is_deleted", 0)
    if active_only:
        query = query.eq("is_active", 1)

    wh_id = None
    try:
        from utils.auth import get_user_warehouse_id
        wh_id = get_user_warehouse_id()
    except (ImportError, Exception):
        pass

    if wh_id:
        query = query.eq("id", wh_id)

    query = query.order("name")
    result = query.execute()
    return pd.DataFrame(result.data) if result.data else pd.DataFrame()


def get_categories_df(active_only=True):
    """Load product categories as DataFrame."""
    sb = get_supabase()
    query = sb.table("product_categories").select("*")
    if active_only:
        query = query.eq("is_active", 1)
    query = query.order("name")
    result = query.execute()
    return pd.DataFrame(result.data) if result.data else pd.DataFrame()


def get_demand_df(filters=None):
    """Load demand records using demand_detail view, optionally filtered."""
    filters = apply_warehouse_isolation(dict(filters) if filters else {})

    sb = get_supabase()
    query = sb.table("demand_detail").select("*")

    if filters:
        if filters.get("warehouse_id"):
            query = query.eq("warehouse_id", filters["warehouse_id"])
        if filters.get("product_id"):
            query = query.eq("product_id", filters["product_id"])
        if filters.get("category_id"):
            query = query.eq("category_id", filters["category_id"])
        if filters.get("status"):
            query = query.eq("status", filters["status"])
        if filters.get("date_from"):
            query = query.gte("demand_date", str(filters["date_from"]))
        if filters.get("date_to"):
            query = query.lte("demand_date", str(filters["date_to"]))
        # For year/month filters, use date ranges instead of strftime
        if filters.get("year") and filters.get("month") and not filters.get("date_from"):
            year = int(filters["year"])
            month = int(filters["month"])
            start = f"{year}-{month:02d}-01"
            if month == 12:
                end = f"{year + 1}-01-01"
            else:
                end = f"{year}-{month + 1:02d}-01"
            query = query.gte("demand_date", start).lt("demand_date", end)
        elif filters.get("year") and not filters.get("month") and not filters.get("date_from"):
            year = int(filters["year"])
            query = query.gte("demand_date", f"{year}-01-01").lt("demand_date", f"{year + 1}-01-01")

    query = query.order("demand_date", desc=True)
    result = query.execute()
    df = pd.DataFrame(result.data) if result.data else pd.DataFrame()

    if not df.empty:
        # Ensure numeric columns
        for col in ["quantity", "delivered", "remaining"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
        df["delivery_pct"] = (df["delivered"] / df["quantity"] * 100).round(1)
    return df


def get_current_stock(warehouse_id=None, product_id=None):
    """Get current stock from stock_summary view."""
    if not warehouse_id:
        try:
            from utils.auth import get_user_warehouse_id
            wh_id = get_user_warehouse_id()
            if wh_id:
                warehouse_id = wh_id
        except (ImportError, Exception):
            pass

    sb = get_supabase()
    query = sb.table("stock_summary").select("*")

    if warehouse_id:
        query = query.eq("warehouse_id", warehouse_id)
    if product_id:
        query = query.eq("product_id", product_id)

    result = query.execute()
    df = pd.DataFrame(result.data) if result.data else pd.DataFrame()

    if not df.empty:
        for col in ["current_stock", "minimum_stock", "buffer_stock"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
        df["current_stock"] = df["current_stock"].clip(lower=0)
        df["stock_status"] = df.apply(lambda r: stock_status_label(
            r["current_stock"], r["minimum_stock"], r["buffer_stock"]
        ), axis=1)
    return df


def stock_status_label(current, minimum, buffer):
    """Return stock status: Green / Yellow / Red."""
    if current <= minimum:
        return "🔴 Critical"
    elif current <= buffer:
        return "🟡 Low"
    return "🟢 Sufficient"


def stock_status_color(status_text):
    """Map status label to CSS color."""
    if "Critical" in str(status_text) or "🔴" in str(status_text):
        return "red"
    elif "Low" in str(status_text) or "🟡" in str(status_text):
        return "orange"
    return "green"


def get_pending_demand(threshold_pct=None):
    """Get demand records with high pending quantities."""
    df = get_demand_df()
    if df.empty:
        return df
    pending = df[df["status"].isin(["Pending", "Partially Dispatched"])].copy()
    if threshold_pct and not pending.empty:
        pending["pending_pct"] = (pending["remaining"] / pending["quantity"] * 100).round(1)
        pending = pending[pending["pending_pct"] >= threshold_pct]
    return pending


def get_attention_products():
    """Identify products that need attention based on multiple rules."""
    stock_df = get_current_stock()
    demand_df = get_demand_df()
    attention = []

    # Rule 1: Stock below minimum
    if not stock_df.empty:
        low = stock_df[stock_df["stock_status"].str.contains("Critical|Low")]
        for _, r in low.iterrows():
            attention.append({
                "product": r["product_name"],
                "warehouse": r["warehouse_name"],
                "reason": f"Stock {r['stock_status']} — Current: {r['current_stock']:.0f}, Min: {r['minimum_stock']:.0f}",
                "severity": "high" if "Critical" in r["stock_status"] else "medium",
            })

    # Rule 2: High pending demand
    if not demand_df.empty:
        pending = demand_df[demand_df["status"].isin(["Pending", "Partially Dispatched"])]
        for _, r in pending.iterrows():
            if r["remaining"] > 0 and r.get("delivery_pct", 100) < 50:
                attention.append({
                    "product": r["product_name"],
                    "warehouse": r["warehouse_name"],
                    "reason": f"High pending — Demand: {r['quantity']:.0f}, Delivered: {r['delivered']:.0f}, Remaining: {r['remaining']:.0f}",
                    "severity": "high",
                })

    # Rule 3: Stock insufficient for pending demand
    if not stock_df.empty and not demand_df.empty:
        pending_totals = demand_df[demand_df["status"].isin(["Pending", "Partially Dispatched"])].groupby(
            ["product_id", "warehouse_id"]
        )["remaining"].sum().reset_index()

        for _, pt in pending_totals.iterrows():
            stock_row = stock_df[
                (stock_df["product_id"] == pt["product_id"]) &
                (stock_df["warehouse_id"] == pt["warehouse_id"])
            ]
            if not stock_row.empty:
                cur = stock_row.iloc[0]["current_stock"]
                if cur < pt["remaining"]:
                    attention.append({
                        "product": stock_row.iloc[0]["product_name"],
                        "warehouse": stock_row.iloc[0]["warehouse_name"],
                        "reason": f"Insufficient stock for pending demand — Stock: {cur:.0f}, Pending: {pt['remaining']:.0f}",
                        "severity": "high",
                    })

    return attention


def format_number(n, decimals=0):
    """Format number with commas."""
    if pd.isna(n):
        return "0"
    return f"{n:,.{decimals}f}"


def apply_sidebar_filters():
    """Render sidebar filters and return filter dict. Used by Dashboard and Reports."""
    filters = {}

    warehouses = get_warehouses_df()
    products = get_products_df()
    categories = get_categories_df()

    st.sidebar.markdown("### 🔍 Filters")

    # Warehouse filter — non-admin users are auto-scoped to their own warehouse
    user_wh_id = None
    try:
        from utils.auth import get_user_warehouse_id
        user_wh_id = get_user_warehouse_id()
    except (ImportError, Exception):
        pass

    if user_wh_id:
        filters["warehouse_id"] = user_wh_id
        if not warehouses.empty:
            st.sidebar.caption(f"🏢 Warehouse: **{warehouses.iloc[0]['name']}**")
    else:
        wh_options = ["All Warehouses"] + warehouses["name"].tolist() if not warehouses.empty else ["All Warehouses"]
        wh_sel = st.sidebar.selectbox("Warehouse / گودام", wh_options)
        if wh_sel != "All Warehouses" and not warehouses.empty:
            filters["warehouse_id"] = int(warehouses[warehouses["name"] == wh_sel].iloc[0]["id"])

    # Category filter
    cat_options = ["All Categories"] + categories["name"].tolist() if not categories.empty else ["All Categories"]
    cat_sel = st.sidebar.selectbox("Category / زمرہ", cat_options)
    if cat_sel != "All Categories" and not categories.empty:
        filters["category_id"] = int(categories[categories["name"] == cat_sel].iloc[0]["id"])

    # Product filter
    prod_options = ["All Products"] + products["name"].tolist() if not products.empty else ["All Products"]
    prod_sel = st.sidebar.selectbox("Product / مصنوعات", prod_options)
    if prod_sel != "All Products" and not products.empty:
        filters["product_id"] = int(products[products["name"] == prod_sel].iloc[0]["id"])

    # Date filter
    st.sidebar.markdown("---")
    date_mode = st.sidebar.radio("Date Range", ["Current Month", "Previous Month", "Custom Range", "All Time"], horizontal=False)

    today = date.today()
    if date_mode == "Current Month":
        filters["date_from"] = today.replace(day=1)
        filters["date_to"] = today
        filters["year"] = today.year
        filters["month"] = today.month
    elif date_mode == "Previous Month":
        first_this = today.replace(day=1)
        last_prev = first_this - pd.Timedelta(days=1)
        filters["date_from"] = last_prev.replace(day=1)
        filters["date_to"] = last_prev
        filters["year"] = last_prev.year
        filters["month"] = last_prev.month
    elif date_mode == "Custom Range":
        col1, col2 = st.sidebar.columns(2)
        filters["date_from"] = col1.date_input("From", today.replace(day=1))
        filters["date_to"] = col2.date_input("To", today)

    # Year comparison toggle
    st.sidebar.markdown("---")
    filters["compare_yoy"] = st.sidebar.checkbox("📊 Compare with last year")

    return filters
