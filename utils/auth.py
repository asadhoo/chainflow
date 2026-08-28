"""
ChainFlow — Authentication & Role-Based Access Control
"""
import base64
import streamlit as st
import bcrypt

from config import JPL_LOGO_B64, APP_NAME, COMPANY_NAME, ROLES, ROLE_PERMISSIONS
from database.db import get_supabase


def authenticate(username, password):
    """Verify username/password against the users table using bcrypt.
    Returns a user dict on success, None on failure."""
    if not username or not password:
        return None

    sb = get_supabase()
    result = sb.table("users").select("*").eq("username", username.strip()).eq("is_active", 1).execute()

    if not result.data:
        return None

    row = result.data[0]

    try:
        if not bcrypt.checkpw(password.encode(), row["password_hash"].encode()):
            return None
    except Exception:
        return None

    return {
        "id": row["id"],
        "username": row["username"],
        "full_name": row.get("full_name") or row["username"],
        "role": row.get("role") or "viewer",
        "warehouse_id": row.get("warehouse_id"),
    }


def _get_warehouse_name(warehouse_id):
    if not warehouse_id:
        return None
    sb = get_supabase()
    result = sb.table("warehouses").select("name").eq("id", warehouse_id).execute()
    return result.data[0]["name"] if result.data else None


def _render_login_page():
    """Render the centered JPL login page."""
    st.markdown(f"""
    <div class="login-wrapper">
        <div class="login-card">
            <img src="data:image/png;base64,{JPL_LOGO_B64}" class="login-logo">
            <h1 class="login-title">{APP_NAME}</h1>
            <p class="login-subtitle">{COMPANY_NAME}</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    _, col, _ = st.columns([1, 1.2, 1])
    with col:
        with st.form("login_form"):
            username = st.text_input("Username / صارف نام")
            password = st.text_input("Password / پاس ورڈ", type="password")
            submitted = st.form_submit_button("🔐 Login", use_container_width=True)

            if submitted:
                user = authenticate(username, password)
                if user:
                    st.session_state["user"] = user
                    st.rerun()
                else:
                    st.error("❌ Invalid username or password. / غلط صارف نام یا پاس ورڈ")

    st.markdown("""
    <div class="login-footer">
        <p>Contact your administrator if you have trouble logging in.</p>
    </div>
    """, unsafe_allow_html=True)


def check_login():
    """Check st.session_state for a logged-in user. Show login page and st.stop()
    if not authenticated. Returns the user dict when authenticated."""
    user = st.session_state.get("user")
    if user:
        return user

    _render_login_page()
    st.stop()


def logout():
    """Clear session state related to the logged-in user."""
    for key in ["user"]:
        if key in st.session_state:
            del st.session_state[key]


def get_current_user():
    """Return the current user dict from session state (or None)."""
    return st.session_state.get("user")


def get_user_warehouse_id():
    """Return the warehouse_id for the current user, or None for admin/unassigned users."""
    user = get_current_user()
    if not user:
        return None
    if user.get("role") == "admin":
        return None
    return user.get("warehouse_id")


def require_role(allowed_roles):
    """Ensure the current user's role is in allowed_roles. Shows an error and
    stops the page if not. Returns the user dict on success."""
    user = get_current_user()
    if not user:
        st.error("🔒 You must be logged in to view this page.")
        st.stop()

    role = user.get("role")
    if role not in allowed_roles:
        st.error(f"⛔ Access denied. Your role (**{ROLES.get(role, role)}**) does not have permission to view this page.")
        st.stop()

    return user


def has_action(action):
    """Check whether the current user's role permits a given action (view/add/edit/delete/...)."""
    user = get_current_user()
    if not user:
        return False
    role = user.get("role")
    perms = ROLE_PERMISSIONS.get(role, {})
    return action in perms.get("actions", [])


def render_sidebar_user_info():
    """Render current user info + logout button in the sidebar."""
    user = get_current_user()
    if not user:
        return

    wh_name = _get_warehouse_name(user.get("warehouse_id")) if user.get("role") != "admin" else None

    st.sidebar.markdown("<div class='section-divider'></div>", unsafe_allow_html=True)
    st.sidebar.markdown(f"""
    <div class="sidebar-user-box">
        <p class="sidebar-user-name">👤 {user['full_name']}</p>
        <p class="sidebar-user-role">{ROLES.get(user['role'], user['role'])}</p>
        {f'<p class="sidebar-user-wh">🏢 {wh_name}</p>' if wh_name else ''}
    </div>
    """, unsafe_allow_html=True)

    if st.sidebar.button("🚪 Logout / لاگ آؤٹ", use_container_width=True):
        logout()
        st.rerun()
