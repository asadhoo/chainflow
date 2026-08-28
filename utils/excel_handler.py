"""
ChainFlow — Excel import/export handler.
"""
import pandas as pd
import io
from datetime import datetime
from database.db import get_supabase


def import_products(df):
    """Import products from validated DataFrame. Returns count imported."""
    sb = get_supabase()
    count = 0
    for _, row in df.iterrows():
        code = str(row.get("code", "")).strip()
        name = str(row.get("name", "")).strip()
        if not code or not name:
            continue
        # Find category
        cat_id = None
        cat_name = str(row.get("category", "")).strip()
        if cat_name:
            cat_result = sb.table("product_categories").select("id").eq("name", cat_name).execute()
            if cat_result.data:
                cat_id = cat_result.data[0]["id"]

        # Check if product already exists
        existing = sb.table("products").select("id").eq("code", code).execute()
        if existing.data:
            continue

        try:
            sb.table("products").insert({
                "code": code,
                "name": name,
                "category_id": cat_id,
                "pack_size": str(row.get("pack_size", "")).strip() or None,
                "packing_type": str(row.get("packing_type", "")).strip() or None,
                "unit": str(row.get("unit", "KG")).strip(),
                "minimum_stock": float(row.get("minimum_stock", 0) or 0),
                "buffer_stock": float(row.get("buffer_stock", 0) or 0),
                "opening_stock": float(row.get("opening_stock", 0) or 0),
            }).execute()
            count += 1
        except Exception:
            continue
    return count


def import_warehouses(df):
    """Import warehouses from validated DataFrame."""
    sb = get_supabase()
    count = 0
    for _, row in df.iterrows():
        code = str(row.get("code", "")).strip()
        name = str(row.get("name", "")).strip()
        if not code or not name:
            continue

        existing = sb.table("warehouses").select("id").eq("code", code).execute()
        if existing.data:
            continue

        try:
            sb.table("warehouses").insert({
                "code": code,
                "name": name,
                "location": str(row.get("location", "")).strip() or None,
            }).execute()
            count += 1
        except Exception:
            continue
    return count


def import_demand(df):
    """Import demand records. Products and warehouses must exist."""
    sb = get_supabase()
    count = 0
    for idx, row in df.iterrows():
        product_name = str(row.get("product", "")).strip()
        warehouse_name = str(row.get("warehouse", "")).strip()

        p = sb.table("products").select("id, category_id").or_(f"name.eq.{product_name},code.eq.{product_name}").execute()
        w = sb.table("warehouses").select("id").or_(f"name.eq.{warehouse_name},code.eq.{warehouse_name}").execute()
        if not p.data or not w.data:
            continue

        prod_data = p.data[0]
        wh_id = w.data[0]["id"]

        # Get or find category
        cat_id = None
        cat_name = str(row.get("category", "")).strip()
        if cat_name:
            cat_result = sb.table("product_categories").select("id").eq("name", cat_name).execute()
            if cat_result.data:
                cat_id = cat_result.data[0]["id"]
        if not cat_id:
            cat_id = prod_data.get("category_id")

        # Generate reference
        ref = str(row.get("reference", "")).strip()
        if not ref:
            today_str = datetime.now().strftime("%Y%m%d")
            pattern = f"DEM-{today_str}-"
            last = sb.table("demand").select("reference").like("reference", f"{pattern}%").order("reference", desc=True).limit(1).execute()
            num = int(last.data[0]["reference"].split("-")[-1]) + 1 if last.data else 1
            ref = f"{pattern}{num:03d}"

        # Check if reference already exists
        existing = sb.table("demand").select("id").eq("reference", ref).execute()
        if existing.data:
            continue

        try:
            demand_date = str(row.get("demand_date", "")).strip()
            required_date = str(row.get("required_date", "")).strip() or None
            sb.table("demand").insert({
                "reference": ref,
                "demand_date": demand_date,
                "required_date": required_date,
                "warehouse_id": wh_id,
                "product_id": prod_data["id"],
                "category_id": cat_id,
                "quantity": float(row.get("quantity", 0)),
                "status": str(row.get("status", "Pending")).strip(),
                "remarks": str(row.get("remarks", "")).strip() or None,
            }).execute()
            count += 1
        except Exception:
            continue
    return count


def import_stock(df):
    """Import stock transactions."""
    sb = get_supabase()
    count = 0
    for _, row in df.iterrows():
        product_name = str(row.get("product", "")).strip()
        warehouse_name = str(row.get("warehouse", "")).strip()

        p = sb.table("products").select("id").or_(f"name.eq.{product_name},code.eq.{product_name}").execute()
        w = sb.table("warehouses").select("id").or_(f"name.eq.{warehouse_name},code.eq.{warehouse_name}").execute()
        if not p.data or not w.data:
            continue

        try:
            sb.table("stock_transactions").insert({
                "transaction_date": str(row.get("transaction_date", "")).strip(),
                "warehouse_id": w.data[0]["id"],
                "product_id": p.data[0]["id"],
                "transaction_type": str(row.get("transaction_type", "received")).strip().lower(),
                "quantity": float(row.get("quantity", 0)),
                "reference": str(row.get("reference", "")).strip() or None,
                "remarks": str(row.get("remarks", "")).strip() or None,
            }).execute()
            count += 1
        except Exception:
            continue
    return count


def export_to_excel(df, sheet_name="Report"):
    """Convert DataFrame to Excel bytes for download."""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
        workbook = writer.book
        worksheet = writer.sheets[sheet_name]

        # Auto-fit columns
        for i, col in enumerate(df.columns):
            try:
                col_max = df[col].astype(str).map(len).max()
                if pd.isna(col_max):
                    col_max = 0
                max_len = int(max(col_max, len(str(col)))) + 2
            except (TypeError, ValueError):
                max_len = len(str(col)) + 2
            worksheet.set_column(i, i, min(max_len, 40))

        # Header format
        header_fmt = workbook.add_format({
            "bold": True, "bg_color": "#2E7D32", "font_color": "#FFFFFF",
            "border": 1, "text_wrap": True
        })
        for i, col in enumerate(df.columns):
            worksheet.write(0, i, col, header_fmt)

    return output.getvalue()


def generate_template(import_type):
    """Generate a blank Excel template for the given import type."""
    templates = {
        "products": pd.DataFrame(columns=[
            "code", "name", "category", "pack_size", "packing_type",
            "unit", "minimum_stock", "buffer_stock", "opening_stock"
        ]),
        "warehouses": pd.DataFrame(columns=["code", "name", "location"]),
        "demand": pd.DataFrame(columns=[
            "demand_date", "warehouse", "product", "category",
            "quantity", "required_date", "status", "remarks"
        ]),
        "dispatch": pd.DataFrame(columns=[
            "dispatch_date", "demand_reference", "quantity", "remarks"
        ]),
        "stock": pd.DataFrame(columns=[
            "transaction_date", "warehouse", "product",
            "transaction_type", "quantity", "reference", "remarks"
        ]),
    }
    df = templates.get(import_type, pd.DataFrame())
    return export_to_excel(df, sheet_name=import_type.title())
