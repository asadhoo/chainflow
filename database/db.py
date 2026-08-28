"""
ChainFlow Database — Supabase connection and helper functions.
"""
import streamlit as st
from supabase import create_client, Client
from config import DEFAULT_SETTINGS, SUPABASE_URL, SUPABASE_KEY


def get_supabase() -> Client:
    """Get or create a cached Supabase client."""
    if "supabase_client" not in st.session_state:
        try:
            url = st.secrets.get("SUPABASE_URL", SUPABASE_URL)
            key = st.secrets.get("SUPABASE_KEY", SUPABASE_KEY)
        except Exception:
            url = SUPABASE_URL
            key = SUPABASE_KEY
        st.session_state["supabase_client"] = create_client(url, key)
    return st.session_state["supabase_client"]


# Keep get_connection as alias for backward compat in imports
get_connection = get_supabase


def init_database():
    """Seed admin user and default data if not present. Tables already exist in Supabase."""
    sb = get_supabase()

    # Seed default settings
    for key, value in DEFAULT_SETTINGS.items():
        existing = sb.table("settings").select("key").eq("key", key).execute()
        if not existing.data:
            sb.table("settings").insert({"key": key, "value": value}).execute()

    # Seed default categories
    default_categories = [
        ("Insecticide", "کیڑے مار دوا"),
        ("Fungicide", "پھپھوندی مار دوا"),
        ("Herbicide", "جڑی بوٹی مار دوا"),
        ("Seed Treatment", "بیج کا علاج"),
        ("Other", "دیگر"),
    ]
    for name, name_urdu in default_categories:
        existing = sb.table("product_categories").select("id").eq("name", name).execute()
        if not existing.data:
            sb.table("product_categories").insert({"name": name, "name_urdu": name_urdu}).execute()

    # Seed default admin user (password: admin123)
    try:
        import bcrypt
        existing = sb.table("users").select("id").eq("username", "admin").execute()
        if not existing.data:
            pw_hash = bcrypt.hashpw(b"admin123", bcrypt.gensalt()).decode()
            sb.table("users").insert({
                "username": "admin",
                "password_hash": pw_hash,
                "full_name": "Administrator",
                "role": "admin",
            }).execute()
    except ImportError:
        pass

    # Seed default warehouse users
    _seed_warehouse_users(sb)


def _seed_warehouse_users(sb: Client):
    """Create default warehouse user accounts if warehouses exist."""
    try:
        import bcrypt
    except ImportError:
        return

    warehouses = [
        ("multan", "Multan@123", "Multan Warehouse", "warehouse_manager", "WH-MLT"),
        ("dgkhan", "DGKhan@123", "DG Khan Warehouse", "warehouse_manager", "WH-DGK"),
        ("bahawalpur", "Bwp@123", "Bahawalpur Warehouse", "warehouse_manager", "WH-BWP"),
        ("khanewal", "Khn@123", "Khanewal Warehouse", "warehouse_manager", "WH-KHN"),
        ("muzaffargarh", "Mzg@123", "Muzaffargarh Warehouse", "warehouse_manager", "WH-MZG"),
    ]
    for username, password, full_name, role, wh_code in warehouses:
        wh_result = sb.table("warehouses").select("id").eq("code", wh_code).execute()
        if wh_result.data:
            existing = sb.table("users").select("id").eq("username", username).execute()
            if not existing.data:
                pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
                sb.table("users").insert({
                    "username": username,
                    "password_hash": pw_hash,
                    "full_name": full_name,
                    "role": role,
                    "warehouse_id": wh_result.data[0]["id"],
                }).execute()


def get_setting(key, default=None):
    """Get a setting value."""
    sb = get_supabase()
    result = sb.table("settings").select("value").eq("key", key).execute()
    if result.data:
        return result.data[0]["value"]
    return default


def set_setting(key, value, description=None):
    """Set a setting value (upsert)."""
    sb = get_supabase()
    row = {"key": key, "value": value}
    if description is not None:
        row["description"] = description
    sb.table("settings").upsert(row, on_conflict="key").execute()


def log_audit(table_name, record_id, action, old_values=None, new_values=None, username="system"):
    """Write an audit log entry."""
    sb = get_supabase()
    sb.table("audit_log").insert({
        "table_name": table_name,
        "record_id": record_id,
        "action": action,
        "old_values": str(old_values) if old_values else None,
        "new_values": str(new_values) if new_values else None,
        "username": username,
    }).execute()
