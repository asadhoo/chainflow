"""
ChainFlow — Data validation helpers for forms and Excel import.
"""
import pandas as pd
from datetime import date
from database.db import get_supabase


def validate_demand_entry(data, conn=None):
    """Validate demand form data. Returns list of error strings."""
    errors = []
    if not data.get("demand_date"):
        errors.append("Demand date is required.")
    if not data.get("warehouse_id"):
        errors.append("Warehouse is required.")
    if not data.get("product_id"):
        errors.append("Product is required.")
    if not data.get("quantity") or data["quantity"] <= 0:
        errors.append("Quantity must be greater than zero.")
    return errors


def validate_dispatch_entry(data, conn=None):
    """Validate dispatch form data."""
    errors = []
    if not data.get("dispatch_date"):
        errors.append("Dispatch date is required.")
    if not data.get("demand_id"):
        errors.append("Demand reference is required.")
    if not data.get("quantity") or data["quantity"] <= 0:
        errors.append("Quantity must be greater than zero.")

    # Check quantity doesn't exceed remaining demand
    if data.get("demand_id") and data.get("quantity"):
        sb = get_supabase()
        result = sb.rpc("get_dispatch_remaining", {"p_demand_id": data["demand_id"]}).execute()
        remaining = result.data if isinstance(result.data, (int, float)) else 0
        if data["quantity"] > remaining:
            errors.append(f"Dispatch quantity ({data['quantity']}) exceeds remaining demand ({remaining:.1f}).")

    return errors


def validate_stock_entry(data, conn=None):
    """Validate stock transaction form data."""
    errors = []
    if not data.get("transaction_date"):
        errors.append("Transaction date is required.")
    if not data.get("warehouse_id"):
        errors.append("Warehouse is required.")
    if not data.get("product_id"):
        errors.append("Product is required.")
    if not data.get("transaction_type"):
        errors.append("Transaction type is required.")
    if data.get("quantity") is None or data["quantity"] <= 0:
        errors.append("Quantity must be greater than zero.")
    return errors


def validate_product_entry(data, conn=None):
    """Validate product form data."""
    errors = []
    if not data.get("code") or not data["code"].strip():
        errors.append("Product code is required.")
    if not data.get("name") or not data["name"].strip():
        errors.append("Product name is required.")

    # Check code uniqueness
    if data.get("code"):
        sb = get_supabase()
        result = sb.table("products").select("id").eq("code", data["code"].strip()).neq("id", data.get("id", 0)).execute()
        if result.data:
            errors.append(f"Product code '{data['code']}' already exists.")
    return errors


def validate_warehouse_entry(data, conn=None):
    """Validate warehouse form data."""
    errors = []
    if not data.get("code") or not data["code"].strip():
        errors.append("Warehouse code is required.")
    if not data.get("name") or not data["name"].strip():
        errors.append("Warehouse name is required.")

    if data.get("code"):
        sb = get_supabase()
        result = sb.table("warehouses").select("id").eq("code", data["code"].strip()).neq("id", data.get("id", 0)).execute()
        if result.data:
            errors.append(f"Warehouse code '{data['code']}' already exists.")
    return errors


def validate_import_dataframe(df, import_type, conn=None):
    """
    Validate an imported DataFrame.
    Returns (clean_df, errors_list) where errors_list has row-level error messages.
    """
    errors = []
    required_cols_map = {
        "products": ["code", "name"],
        "warehouses": ["code", "name"],
        "demand": ["demand_date", "warehouse", "product", "quantity"],
        "dispatch": ["dispatch_date", "demand_reference", "quantity"],
        "stock": ["transaction_date", "warehouse", "product", "transaction_type", "quantity"],
    }

    # Column name aliases
    column_aliases = {
        "product_code": "code", "product code": "code", "item_code": "code", "item code": "code",
        "product_name": "name", "product name": "name", "item_name": "name", "item name": "name",
        "warehouse_code": "code", "warehouse code": "code",
        "warehouse_name": "warehouse", "warehouse name": "warehouse",
        "product_id": "product", "warehouse_id": "warehouse",
        "date": "demand_date", "demand date": "demand_date",
        "dispatch date": "dispatch_date", "transaction date": "transaction_date",
        "type": "transaction_type", "transaction type": "transaction_type",
        "qty": "quantity", "amount": "quantity",
        "demand_ref": "demand_reference", "demand ref": "demand_reference",
        "reference": "demand_reference", "ref": "demand_reference",
        "size": "pack_size", "pack size": "pack_size",
        "packing": "packing_type", "packing type": "packing_type",
        "min_stock": "minimum_stock", "minimum stock": "minimum_stock",
        "buffer": "buffer_stock", "buffer stock": "buffer_stock",
        "opening": "opening_stock", "opening stock": "opening_stock",
    }

    required = required_cols_map.get(import_type, [])
    # Normalise column names
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    # Apply aliases
    rename_map = {}
    for col in df.columns:
        col_clean = col.strip().lower().replace("_", " ")
        if col not in required and col_clean in column_aliases:
            rename_map[col] = column_aliases[col_clean]
        elif col not in required and col in column_aliases:
            rename_map[col] = column_aliases[col]
    if rename_map:
        df.rename(columns=rename_map, inplace=True)

    # Check required columns
    for col in required:
        if col not in df.columns:
            errors.append(f"Missing required column: '{col}'")

    if errors:
        return df, errors

    sb = get_supabase()

    # Row-level validation
    for idx, row in df.iterrows():
        row_num = idx + 2  # Excel rows start at 1 + header row
        for col in required:
            val = row.get(col)
            if pd.isna(val) or (isinstance(val, str) and not val.strip()):
                errors.append(f"Row {row_num}: '{col}' is empty.")

        if "quantity" in required:
            qty = row.get("quantity")
            if not pd.isna(qty):
                try:
                    q = float(qty)
                    if q <= 0:
                        errors.append(f"Row {row_num}: Quantity must be greater than 0.")
                except (ValueError, TypeError):
                    errors.append(f"Row {row_num}: Invalid quantity value '{qty}'.")

        # Check product/warehouse exist
        if import_type in ("demand", "stock"):
            product_name = row.get("product")
            if not pd.isna(product_name):
                val = str(product_name).strip()
                p = sb.table("products").select("id").or_(f"name.eq.{val},code.eq.{val}").execute()
                if not p.data:
                    errors.append(f"Row {row_num}: Product '{product_name}' not found. Add it first.")

            warehouse_name = row.get("warehouse")
            if not pd.isna(warehouse_name):
                val = str(warehouse_name).strip()
                w = sb.table("warehouses").select("id").or_(f"name.eq.{val},code.eq.{val}").execute()
                if not w.data:
                    errors.append(f"Row {row_num}: Warehouse '{warehouse_name}' not found. Add it first.")

    return df, errors
