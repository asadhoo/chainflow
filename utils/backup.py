"""
ChainFlow — Database backup utility.
With Supabase, backups are managed server-side. These functions are kept as stubs
to avoid import errors from the Settings page.
"""


def create_backup():
    """No-op for Supabase — backups are managed server-side."""
    return "(Supabase managed backup)"


def list_backups():
    """No backups to list for Supabase."""
    return []


def restore_backup(filename):
    """Not applicable for Supabase."""
    return False


def delete_old_backups(keep=10):
    """Not applicable for Supabase."""
    return 0
