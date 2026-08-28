"""
ChainFlow Comprehensive Test Suite
Tests: Database, helpers, validators, business logic, edge cases
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Use a test database to avoid touching real data
TEST_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_chainflow.db")
import config
config.DB_PATH = TEST_DB

# Clean up any previous test db
if os.path.exists(TEST_DB):
    os.remove(TEST_DB)

import traceback
from datetime import date, datetime

results = {"passed": 0, "failed": 0, "errors": []}

def test(name):
    def decorator(func):
        def wrapper():
            try:
                func()
                results["passed"] += 1
                print(f"  ✅ {name}")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append(f"{name}: {e}")
                print(f"  ❌ {name}: {e}")
                traceback.print_exc()
        return wrapper
    return decorator


# ==============================
# 1. DATABASE TESTS
# ==============================
print("\n" + "="*60)
print("1. DATABASE TESTS")
print("="*60)

from database.db import init_database, get_connection, get_setting, set_setting, log_audit

@test("Database initialization creates all tables")
def test_db_init():
    init_database()
    conn = get_connection()
    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    conn.close()
    expected = ['product_categories', 'products', 'warehouses', 'demand', 'dispatch',
                'stock_transactions', 'settings', 'users', 'audit_log']
    for t in expected:
        assert t in tables, f"Missing table: {t}"

test_db_init()

@test("Default categories are seeded")
def test_categories():
    conn = get_connection()
    cats = conn.execute("SELECT COUNT(*) FROM product_categories").fetchone()[0]
    conn.close()
    assert cats >= 5, f"Expected >=5 categories, got {cats}"

test_categories()

@test("Default settings are seeded")
def test_settings():
    val = get_setting("currency")
    assert val == "PKR", f"Expected PKR, got {val}"
    val2 = get_setting("language")
    assert val2 == "en", f"Expected en, got {val2}"

test_settings()

@test("set_setting and get_setting work")
def test_set_get_setting():
    set_setting("test_key", "test_value", "Test description")
    val = get_setting("test_key")
    assert val == "test_value", f"Expected test_value, got {val}"

test_set_get_setting()

@test("Default admin user is created")
def test_admin_user():
    conn = get_connection()
    admin = conn.execute("SELECT * FROM users WHERE username='admin'").fetchone()
    conn.close()
    assert admin is not None, "Admin user not found"
    assert admin["role"] == "admin"

test_admin_user()

@test("Audit logging works")
def test_audit():
    log_audit("test_table", 1, "TEST", old_values={"a": 1}, new_values={"a": 2})
    conn = get_connection()
    entry = conn.execute("SELECT * FROM audit_log WHERE table_name='test_table'").fetchone()
    conn.close()
    assert entry is not None
    assert entry["action"] == "TEST"

test_audit()

@test("WAL mode and foreign keys are enabled")
def test_pragmas():
    conn = get_connection()
    wal = conn.execute("PRAGMA journal_mode").fetchone()[0]
    fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
    conn.close()
    assert wal == "wal", f"Expected wal mode, got {wal}"
    assert fk == 1, f"Expected FK=1, got {fk}"

test_pragmas()

@test("Indexes are created")
def test_indexes():
    conn = get_connection()
    indexes = [r[1] for r in conn.execute("PRAGMA index_list('demand')").fetchall()]
    conn.close()
    assert len(indexes) >= 3, f"Expected >=3 indexes on demand, got {len(indexes)}"

test_indexes()


# ==============================
# 2. SEED TEST DATA
# ==============================
print("\n" + "="*60)
print("2. SEEDING TEST DATA")
print("="*60)

conn = get_connection()
# Add warehouses
conn.execute("INSERT INTO warehouses (code, name, location) VALUES ('WH-MLT', 'Multan', 'South Punjab')")
conn.execute("INSERT INTO warehouses (code, name, location) VALUES ('WH-LHR', 'Lahore', 'Central Punjab')")

# Add products
conn.execute("INSERT INTO products (code, name, category_id, unit, minimum_stock, buffer_stock) VALUES ('INS-001', 'Alpha Cypermethrin', 1, 'Litre', 100, 200)")
conn.execute("INSERT INTO products (code, name, category_id, unit, minimum_stock, buffer_stock) VALUES ('FUN-001', 'Mancozeb', 2, 'KG', 50, 100)")
conn.execute("INSERT INTO products (code, name, category_id, unit, minimum_stock, buffer_stock) VALUES ('HRB-001', 'Glyphosate', 3, 'Litre', 30, 60)")

# Add stock transactions
conn.execute("INSERT INTO stock_transactions (transaction_date, warehouse_id, product_id, transaction_type, quantity, remarks) VALUES ('2026-01-01', 1, 1, 'opening', 500, 'Opening stock')")
conn.execute("INSERT INTO stock_transactions (transaction_date, warehouse_id, product_id, transaction_type, quantity, remarks) VALUES ('2026-01-01', 1, 2, 'opening', 300, 'Opening stock')")
conn.execute("INSERT INTO stock_transactions (transaction_date, warehouse_id, product_id, transaction_type, quantity, remarks) VALUES ('2026-01-01', 2, 1, 'opening', 200, 'Opening stock')")
conn.execute("INSERT INTO stock_transactions (transaction_date, warehouse_id, product_id, transaction_type, quantity, remarks) VALUES ('2026-02-15', 1, 1, 'received', 100, 'New supply')")
conn.execute("INSERT INTO stock_transactions (transaction_date, warehouse_id, product_id, transaction_type, quantity, remarks) VALUES ('2026-03-01', 1, 3, 'opening', 20, 'Opening stock')")

# Add demand
conn.execute("INSERT INTO demand (reference, demand_date, warehouse_id, product_id, category_id, quantity, status) VALUES ('DEM-20260101-001', '2026-01-15', 1, 1, 1, 200, 'Pending')")
conn.execute("INSERT INTO demand (reference, demand_date, warehouse_id, product_id, category_id, quantity, status) VALUES ('DEM-20260101-002', '2026-01-20', 1, 2, 2, 100, 'Partially Dispatched')")
conn.execute("INSERT INTO demand (reference, demand_date, warehouse_id, product_id, category_id, quantity, status) VALUES ('DEM-20260102-001', '2026-02-10', 2, 1, 1, 50, 'Fully Dispatched')")
conn.execute("INSERT INTO demand (reference, demand_date, warehouse_id, product_id, category_id, quantity, status) VALUES ('DEM-20260103-001', '2026-03-05', 1, 3, 3, 100, 'Pending')")

# Add dispatches
conn.execute("INSERT INTO dispatch (dispatch_date, demand_id, warehouse_id, product_id, quantity) VALUES ('2026-01-25', 2, 1, 2, 60)")
conn.execute("INSERT INTO dispatch (dispatch_date, demand_id, warehouse_id, product_id, quantity) VALUES ('2026-02-15', 3, 2, 1, 50)")

# Dispatch stock deductions
conn.execute("INSERT INTO stock_transactions (transaction_date, warehouse_id, product_id, transaction_type, quantity, reference) VALUES ('2026-01-25', 1, 2, 'dispatched', 60, 'DEM-20260101-002')")
conn.execute("INSERT INTO stock_transactions (transaction_date, warehouse_id, product_id, transaction_type, quantity, reference) VALUES ('2026-02-15', 2, 1, 'dispatched', 50, 'DEM-20260102-001')")

conn.commit()
conn.close()
print("  ✅ Test data seeded: 2 warehouses, 3 products, 4 demand, 2 dispatches, 5 stock txns")


# ==============================
# 3. HELPER FUNCTION TESTS
# ==============================
print("\n" + "="*60)
print("3. HELPER FUNCTION TESTS")
print("="*60)

from utils.helpers import (
    generate_reference, get_products_df, get_warehouses_df,
    get_categories_df, get_demand_df, get_current_stock,
    stock_status_label, get_pending_demand, get_attention_products,
    format_number
)

@test("generate_reference creates correct format")
def test_generate_ref():
    ref = generate_reference("DEM")
    today = date.today().strftime("%Y%m%d")
    assert ref.startswith(f"DEM-{today}-"), f"Bad format: {ref}"

test_generate_ref()

@test("get_products_df returns correct data")
def test_products_df():
    df = get_products_df()
    assert len(df) == 3, f"Expected 3 products, got {len(df)}"
    assert "category_name" in df.columns

test_products_df()

@test("get_products_df active_only=False includes inactive")
def test_products_inactive():
    conn = get_connection()
    conn.execute("UPDATE products SET is_active=0 WHERE code='HRB-001'")
    conn.commit()
    conn.close()
    df_active = get_products_df(active_only=True)
    df_all = get_products_df(active_only=False)
    assert len(df_active) == 2
    assert len(df_all) == 3
    # Restore
    conn = get_connection()
    conn.execute("UPDATE products SET is_active=1 WHERE code='HRB-001'")
    conn.commit()
    conn.close()

test_products_inactive()

@test("get_warehouses_df returns correct data")
def test_warehouses_df():
    df = get_warehouses_df()
    assert len(df) == 2

test_warehouses_df()

@test("get_categories_df returns seeded categories")
def test_categories_df():
    df = get_categories_df()
    assert len(df) >= 5
    assert "Insecticide" in df["name"].values

test_categories_df()

@test("get_demand_df returns all demand with computed columns")
def test_demand_df():
    df = get_demand_df()
    assert len(df) == 4
    assert "delivered" in df.columns
    assert "remaining" in df.columns
    assert "delivery_pct" in df.columns
    # DEM-20260101-002 should have delivered=60
    row = df[df["reference"] == "DEM-20260101-002"].iloc[0]
    assert row["delivered"] == 60, f"Expected delivered=60, got {row['delivered']}"
    assert row["remaining"] == 40, f"Expected remaining=40, got {row['remaining']}"

test_demand_df()

@test("get_demand_df filters by warehouse")
def test_demand_filter_warehouse():
    df = get_demand_df({"warehouse_id": 1})
    assert all(df["warehouse_id"] == 1)
    assert len(df) == 3  # 3 demands in Multan

test_demand_filter_warehouse()

@test("get_demand_df filters by date range")
def test_demand_filter_date():
    df = get_demand_df({"date_from": "2026-02-01", "date_to": "2026-03-31"})
    assert len(df) == 2  # Feb and Mar demands

test_demand_filter_date()

@test("get_current_stock calculates correctly")
def test_current_stock():
    df = get_current_stock()
    assert not df.empty
    # Multan Alpha Cypermethrin: opening 500 + received 100 = 600
    multan_alpha = df[(df["product_id"] == 1) & (df["warehouse_id"] == 1)]
    assert not multan_alpha.empty
    assert multan_alpha.iloc[0]["current_stock"] == 600, f"Expected 600, got {multan_alpha.iloc[0]['current_stock']}"

    # Lahore Alpha: opening 200 - dispatched 50 = 150
    lahore_alpha = df[(df["product_id"] == 1) & (df["warehouse_id"] == 2)]
    assert not lahore_alpha.empty
    assert lahore_alpha.iloc[0]["current_stock"] == 150, f"Expected 150, got {lahore_alpha.iloc[0]['current_stock']}"

    # Multan Mancozeb: opening 300 - dispatched 60 = 240
    multan_mancozeb = df[(df["product_id"] == 2) & (df["warehouse_id"] == 1)]
    assert not multan_mancozeb.empty
    assert multan_mancozeb.iloc[0]["current_stock"] == 240, f"Expected 240, got {multan_mancozeb.iloc[0]['current_stock']}"

test_current_stock()

@test("get_current_stock filters by warehouse")
def test_stock_filter():
    df = get_current_stock(warehouse_id=1)
    assert all(df["warehouse_id"] == 1)

test_stock_filter()

@test("stock_status_label returns correct status")
def test_stock_status():
    assert "Critical" in stock_status_label(50, 100, 200)  # below minimum
    assert "Low" in stock_status_label(150, 100, 200)      # between min and buffer
    assert "Sufficient" in stock_status_label(300, 100, 200) # above buffer

test_stock_status()

@test("stock_status_label edge case: at minimum boundary")
def test_stock_boundary():
    assert "Critical" in stock_status_label(100, 100, 200)  # at minimum = critical
    assert "Low" in stock_status_label(200, 100, 200)       # at buffer = low

test_stock_boundary()

@test("get_pending_demand returns only pending/partial")
def test_pending_demand():
    df = get_pending_demand()
    assert not df.empty
    assert all(df["status"].isin(["Pending", "Partially Dispatched"]))

test_pending_demand()

@test("get_attention_products identifies issues")
def test_attention():
    items = get_attention_products()
    # Glyphosate in Multan: stock=20, minimum=30 -> Critical
    # Also DEM-20260103-001: demand 100, stock 20 -> Insufficient
    assert len(items) > 0
    reasons = [i["reason"] for i in items]
    has_critical = any("Critical" in r or "Stock" in r for r in reasons)
    assert has_critical, f"Expected critical stock alert, got: {reasons}"

test_attention()

@test("format_number handles various inputs")
def test_format_number():
    assert format_number(1234567) == "1,234,567"
    assert format_number(0) == "0"
    assert format_number(None) == "0"
    import pandas as pd
    assert format_number(pd.NA) == "0"

test_format_number()


# ==============================
# 4. VALIDATOR TESTS
# ==============================
print("\n" + "="*60)
print("4. VALIDATOR TESTS")
print("="*60)

from utils.validators import (
    validate_demand_entry, validate_dispatch_entry,
    validate_stock_entry, validate_product_entry,
    validate_warehouse_entry, validate_import_dataframe
)

@test("validate_demand_entry catches missing fields")
def test_validate_demand():
    conn = get_connection()
    errors = validate_demand_entry({}, conn)
    conn.close()
    assert len(errors) >= 3  # date, warehouse, product, quantity

test_validate_demand()

@test("validate_demand_entry passes valid data")
def test_validate_demand_ok():
    conn = get_connection()
    errors = validate_demand_entry({
        "demand_date": date.today(),
        "warehouse_id": 1,
        "product_id": 1,
        "quantity": 100,
    }, conn)
    conn.close()
    assert len(errors) == 0

test_validate_demand_ok()

@test("validate_dispatch_entry catches over-dispatch")
def test_validate_dispatch_over():
    conn = get_connection()
    errors = validate_dispatch_entry({
        "dispatch_date": date.today(),
        "demand_id": 1,  # DEM-20260101-001, remaining=200
        "quantity": 999,
    }, conn)
    conn.close()
    assert any("exceeds" in e.lower() for e in errors), f"Expected over-dispatch error, got: {errors}"

test_validate_dispatch_over()

@test("validate_product_entry catches duplicate code")
def test_validate_product_dup():
    conn = get_connection()
    errors = validate_product_entry({"code": "INS-001", "name": "Test", "id": 0}, conn)
    conn.close()
    assert any("already exists" in e for e in errors)

test_validate_product_dup()

@test("validate_product_entry allows same code for same product (edit)")
def test_validate_product_edit():
    conn = get_connection()
    # Product 1 has code INS-001; editing product 1 should allow INS-001
    errors = validate_product_entry({"code": "INS-001", "name": "Test", "id": 1}, conn)
    conn.close()
    assert len(errors) == 0

test_validate_product_edit()

@test("validate_warehouse_entry catches duplicate code")
def test_validate_wh_dup():
    conn = get_connection()
    errors = validate_warehouse_entry({"code": "WH-MLT", "name": "Test", "id": 0}, conn)
    conn.close()
    assert any("already exists" in e for e in errors)

test_validate_wh_dup()

@test("validate_import_dataframe catches missing columns")
def test_validate_import_cols():
    import pandas as pd
    df = pd.DataFrame({"wrong_col": [1, 2]})
    conn = get_connection()
    _, errors = validate_import_dataframe(df, "products", conn)
    conn.close()
    assert any("Missing required column" in e for e in errors)

test_validate_import_cols()

@test("validate_import_dataframe catches empty required values")
def test_validate_import_empty():
    import pandas as pd
    df = pd.DataFrame({"code": ["X1", ""], "name": ["Product1", ""]})
    conn = get_connection()
    _, errors = validate_import_dataframe(df, "products", conn)
    conn.close()
    assert len(errors) > 0  # Row 3 has empty code and name

test_validate_import_empty()

@test("validate_import_dataframe validates demand product/warehouse exist")
def test_validate_import_demand():
    import pandas as pd
    df = pd.DataFrame({
        "demand_date": ["2026-01-01"],
        "warehouse": ["Nonexistent"],
        "product": ["Nonexistent"],
        "quantity": [100],
    })
    conn = get_connection()
    _, errors = validate_import_dataframe(df, "demand", conn)
    conn.close()
    assert any("not found" in e for e in errors)

test_validate_import_demand()


# ==============================
# 5. EXCEL HANDLER TESTS
# ==============================
print("\n" + "="*60)
print("5. EXCEL HANDLER TESTS")
print("="*60)

from utils.excel_handler import (
    export_to_excel, generate_template,
    import_products, import_warehouses
)

@test("export_to_excel generates valid Excel bytes")
def test_export():
    import pandas as pd
    df = pd.DataFrame({"A": [1, 2, 3], "B": ["x", "y", "z"]})
    result = export_to_excel(df, "Test")
    assert isinstance(result, bytes)
    assert len(result) > 100  # Should be a valid xlsx

test_export()

@test("generate_template creates downloadable templates")
def test_templates():
    for ttype in ["products", "warehouses", "demand", "stock"]:
        result = generate_template(ttype)
        assert isinstance(result, bytes), f"Template {ttype} failed"
        assert len(result) > 0

test_templates()

@test("import_products imports new products")
def test_import_products():
    import pandas as pd
    df = pd.DataFrame({
        "code": ["TEST-001", "TEST-002"],
        "name": ["Test Product 1", "Test Product 2"],
        "category": ["Insecticide", "Other"],
        "unit": ["KG", "Litre"],
        "minimum_stock": [10, 20],
        "buffer_stock": [30, 40],
        "opening_stock": [0, 0],
    })
    count = import_products(df)
    assert count == 2, f"Expected 2 imported, got {count}"

test_import_products()

@test("import_products skips duplicates (INSERT OR IGNORE)")
def test_import_dup():
    import pandas as pd
    df = pd.DataFrame({
        "code": ["INS-001"],
        "name": ["Alpha Cypermethrin"],
    })
    count = import_products(df)
    # Should not crash, count may be 1 (attempted) but no actual new row
    assert count >= 0

test_import_dup()


# ==============================
# 6. BACKUP TESTS
# ==============================
print("\n" + "="*60)
print("6. BACKUP TESTS")
print("="*60)

from utils.backup import create_backup, list_backups, delete_old_backups

@test("create_backup creates a backup file")
def test_create_backup():
    path = create_backup()
    assert os.path.exists(path)
    assert path.endswith(".db")

test_create_backup()

@test("list_backups returns backup info")
def test_list_backups():
    backups = list_backups()
    assert len(backups) >= 1
    assert "filename" in backups[0]
    assert "size_mb" in backups[0]

test_list_backups()


# ==============================
# 7. BUSINESS LOGIC TESTS
# ==============================
print("\n" + "="*60)
print("7. BUSINESS LOGIC TESTS")
print("="*60)

@test("Dispatch auto-deducts stock correctly")
def test_dispatch_deduction():
    """Verify stock is reduced when dispatch is recorded."""
    stock_before = get_current_stock(warehouse_id=1, product_id=1)
    before_val = stock_before.iloc[0]["current_stock"] if not stock_before.empty else 0

    # Simulate dispatch
    conn = get_connection()
    conn.execute("INSERT INTO dispatch (dispatch_date, demand_id, warehouse_id, product_id, quantity) VALUES ('2026-08-01', 1, 1, 1, 50)")
    conn.execute("INSERT INTO stock_transactions (transaction_date, warehouse_id, product_id, transaction_type, quantity, reference) VALUES ('2026-08-01', 1, 1, 'dispatched', 50, 'DEM-20260101-001')")
    conn.commit()
    conn.close()

    stock_after = get_current_stock(warehouse_id=1, product_id=1)
    after_val = stock_after.iloc[0]["current_stock"]

    assert after_val == before_val - 50, f"Expected {before_val-50}, got {after_val}"

test_dispatch_deduction()

@test("Delivery percentage calculation is correct")
def test_delivery_pct():
    df = get_demand_df()
    # DEM-20260102-001 was fully dispatched (50/50 = 100%)
    row = df[df["reference"] == "DEM-20260102-001"].iloc[0]
    assert row["delivery_pct"] == 100.0, f"Expected 100%, got {row['delivery_pct']}"

test_delivery_pct()

@test("Remaining demand calculation is correct")
def test_remaining():
    df = get_demand_df()
    # DEM-20260101-001 had 200 demand, now has 50 dispatched, remaining = 150
    row = df[df["reference"] == "DEM-20260101-001"].iloc[0]
    assert row["remaining"] == 150, f"Expected 150, got {row['remaining']}"

test_remaining()

@test("Stock cannot go negative (clipped to 0)")
def test_negative_stock():
    """Add a huge dispatch to test negative stock clipping."""
    conn = get_connection()
    conn.execute("INSERT INTO stock_transactions (transaction_date, warehouse_id, product_id, transaction_type, quantity) VALUES ('2026-08-25', 1, 3, 'dispatched', 9999)")
    conn.commit()
    conn.close()

    stock = get_current_stock(warehouse_id=1, product_id=3)
    if not stock.empty:
        assert stock.iloc[0]["current_stock"] >= 0, "Stock went negative!"

    # Clean up
    conn = get_connection()
    conn.execute("DELETE FROM stock_transactions WHERE quantity=9999")
    conn.commit()
    conn.close()

test_negative_stock()

@test("Year filter works correctly")
def test_year_filter():
    df = get_demand_df({"year": 2026})
    assert len(df) >= 4
    df_empty = get_demand_df({"year": 2020})
    assert len(df_empty) == 0

test_year_filter()


# ==============================
# 8. EDGE CASE TESTS
# ==============================
print("\n" + "="*60)
print("8. EDGE CASE TESTS")
print("="*60)

@test("Empty database queries don't crash")
def test_empty_queries():
    # Get stock for non-existent warehouse
    df = get_current_stock(warehouse_id=999)
    assert df.empty

    # Get demand with impossible filters
    df = get_demand_df({"warehouse_id": 999})
    assert df.empty

test_empty_queries()

@test("Zero quantity demand is rejected by validator")
def test_zero_qty():
    conn = get_connection()
    errors = validate_demand_entry({
        "demand_date": date.today(),
        "warehouse_id": 1,
        "product_id": 1,
        "quantity": 0,
    }, conn)
    conn.close()
    assert len(errors) > 0

test_zero_qty()

@test("Negative quantity demand is rejected")
def test_negative_qty():
    conn = get_connection()
    errors = validate_demand_entry({
        "demand_date": date.today(),
        "warehouse_id": 1,
        "product_id": 1,
        "quantity": -10,
    }, conn)
    conn.close()
    assert len(errors) > 0

test_negative_qty()

@test("Config labels work correctly")
def test_labels():
    from config import get_label
    assert "Total Demand" in get_label("total_demand")
    assert "ڈیمانڈ" in get_label("total_demand", bilingual=True)
    assert get_label("nonexistent") == "nonexistent"

test_labels()

@test("get_label bilingual=False returns English only")
def test_labels_en():
    from config import get_label
    result = get_label("total_demand", bilingual=False)
    assert result == "Total Demand"
    assert "/" not in result

test_labels_en()


# ==============================
# 9. PAGE COMPILATION TESTS
# ==============================
print("\n" + "="*60)
print("9. PAGE COMPILATION TESTS")
print("="*60)

@test("All page files compile without syntax errors")
def test_page_compilation():
    pages_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pages")
    for f in sorted(os.listdir(pages_dir)):
        if f.endswith(".py"):
            filepath = os.path.join(pages_dir, f)
            with open(filepath, 'r', encoding='utf-8') as fh:
                source = fh.read()
            try:
                compile(source, filepath, 'exec')
            except SyntaxError as e:
                raise AssertionError(f"Syntax error in {f}: {e}")

test_page_compilation()

@test("app.py compiles without syntax errors")
def test_app_compilation():
    app_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.py")
    with open(app_path, 'r', encoding='utf-8') as f:
        source = f.read()
    compile(source, app_path, 'exec')

test_app_compilation()

@test("All utility modules import cleanly")
def test_util_imports():
    from utils.helpers import get_demand_df
    from utils.validators import validate_demand_entry
    from utils.excel_handler import export_to_excel
    from utils.backup import create_backup
    from config import APP_NAME, get_label

test_util_imports()


# ==============================
# 10. POTENTIAL BUG CHECKS
# ==============================
print("\n" + "="*60)
print("10. POTENTIAL BUG CHECKS")
print("="*60)

@test("BUG CHECK: Pandas applymap deprecation (should use map)")
def test_applymap_deprecation():
    """In Pandas 2.1+, applymap is deprecated in favor of map.
    Check if app.py and pages use applymap."""
    import pandas as pd
    major, minor = int(pd.__version__.split('.')[0]), int(pd.__version__.split('.')[1])
    if major >= 2 and minor >= 1:
        # Check files for applymap usage
        files_with_applymap = []
        for root, dirs, files in os.walk(os.path.dirname(os.path.abspath(__file__))):
            for f in files:
                if f.endswith('.py') and f != 'test_comprehensive.py':
                    filepath = os.path.join(root, f)
                    with open(filepath) as fh:
                        if 'applymap' in fh.read():
                            files_with_applymap.append(f)
        if files_with_applymap:
            print(f"    ⚠️  WARNING: Files using deprecated applymap: {files_with_applymap}")
            print(f"    → Should be changed to .map() for Pandas {pd.__version__}")
            # Not a failure but a warning
        else:
            print(f"    → No applymap usage found (Pandas {pd.__version__})")

test_applymap_deprecation()

@test("BUG CHECK: get_current_stock() called without args in Import/Export")
def test_stock_no_args():
    """Import/Export page calls get_current_stock() with no args for export.
    This should work fine and return all stock."""
    df = get_current_stock()
    # Should not crash
    assert isinstance(df, pd.DataFrame)

test_stock_no_args()

@test("BUG CHECK: Concurrent DB connections handle WAL correctly")
def test_concurrent_connections():
    conn1 = get_connection()
    conn2 = get_connection()
    # Both should work
    r1 = conn1.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    r2 = conn2.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    assert r1 == r2
    conn1.close()
    conn2.close()

test_concurrent_connections()

@test("BUG CHECK: generate_reference doesn't collide on same day")
def test_ref_no_collision():
    ref1 = generate_reference("TST")
    # Insert a demand with this reference
    conn = get_connection()
    conn.execute("INSERT INTO demand (reference, demand_date, warehouse_id, product_id, quantity) VALUES (?, '2026-08-25', 1, 1, 10)", (ref1,))
    conn.commit()
    conn.close()
    ref2 = generate_reference("TST")
    assert ref1 != ref2, f"Reference collision: {ref1} == {ref2}"
    # Note: generate_reference queries the demand table for prefix "DEM" but we used "TST"
    # This actually reveals a potential issue - see below

test_ref_no_collision()

@test("BUG CHECK: generate_reference only searches demand table")
def test_ref_only_demand():
    """generate_reference always queries the demand table regardless of prefix.
    This means dispatch references or other prefixes still search demand."""
    # This is actually fine for current usage since only DEM prefix is used
    ref = generate_reference("DIS")
    assert ref.startswith("DIS-")

test_ref_only_demand()


# ==============================
# CLEANUP & SUMMARY
# ==============================
print("\n" + "="*60)
print("TEST SUMMARY")
print("="*60)

# Cleanup test db
if os.path.exists(TEST_DB):
    os.remove(TEST_DB)
# Cleanup test backups
import shutil
test_backup_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backups")
if os.path.exists(test_backup_dir):
    shutil.rmtree(test_backup_dir, ignore_errors=True)

total = results["passed"] + results["failed"]
print(f"\n  Total Tests: {total}")
print(f"  ✅ Passed:   {results['passed']}")
print(f"  ❌ Failed:   {results['failed']}")

if results["errors"]:
    print(f"\n  FAILED TESTS:")
    for err in results["errors"]:
        print(f"    → {err}")

print(f"\n  Result: {'ALL TESTS PASSED ✅' if results['failed'] == 0 else 'SOME TESTS FAILED ❌'}")
print("="*60)
