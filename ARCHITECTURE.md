# ChainFlow — Supply Chain Dashboard Architecture

## Version: 1.0.0
## Date: 2026-08-25
## Status: MVP Complete — Ready for Testing

---

## A. Technology Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| Frontend | Streamlit | No coding needed, instant web UI, Python-native |
| Database | SQLite | Zero setup, single file, works on any Windows PC |
| Data | Pandas | Industry-standard for data manipulation |
| Charts | Plotly | Interactive, professional, export-ready charts |
| Excel | openpyxl + xlsxwriter | Read/write Excel files natively |
| Security | bcrypt | Password hashing for user authentication |

---

## B. Project Structure

```
chainflow/
├── app.py                      # Main Dashboard (home page)
├── config.py                   # App configuration & bilingual labels
├── requirements.txt            # Python dependencies
├── INSTALL.bat                 # Windows installer script
├── RUN.bat                     # Windows launcher script
├── ARCHITECTURE.md             # This document
├── chainflow.db                # SQLite database (auto-created)
│
├── .streamlit/
│   └── config.toml             # Streamlit theme (green/white)
│
├── assets/
│   └── style.css               # Custom CSS styling
│
├── database/
│   ├── __init__.py
│   └── db.py                   # DB init, schema, helpers, audit
│
├── utils/
│   ├── __init__.py
│   ├── helpers.py              # Query helpers, KPI calculations, filters
│   ├── validators.py           # Form & import data validation
│   ├── excel_handler.py        # Excel import/export logic
│   └── backup.py               # Database backup/restore
│
├── pages/
│   ├── 1_📦_Demand.py          # Demand entry & management
│   ├── 2_🚚_Dispatch.py        # Dispatch recording & tracking
│   ├── 3_🏭_Stock.py           # Stock levels & transactions
│   ├── 4_🧪_Products.py        # Product master data
│   ├── 5_🏢_Warehouses.py      # Warehouse master data
│   ├── 6_📈_Reports.py         # 7 report types with charts
│   ├── 7_📥_Import_Export.py    # Excel import/export & templates
│   └── 8_⚙️_Settings.py        # Config, backup, data management
│
└── backups/                    # Database backup files
```

---

## C. Database Schema

### Tables (10 total)

1. **product_categories** — Insecticide, Fungicide, Herbicide, etc.
2. **products** — Product master with code, name, pack size, stock thresholds
3. **warehouses** — Warehouse locations (Multan, DG Khan, Bahawalpur, etc.)
4. **demand** — Demand orders with dates, quantities, status tracking
5. **dispatch** — Dispatch records linked to demand (many-to-one)
6. **stock_transactions** — All stock movements (opening, received, dispatched, adjustment)
7. **settings** — Key-value app configuration
8. **users** — Simple authentication (admin/user roles)
9. **audit_log** — Change tracking for data modifications

### Key Relationships
- demand → products (FK), warehouses (FK), product_categories (FK)
- dispatch → demand (FK), products (FK), warehouses (FK)
- stock_transactions → products (FK), warehouses (FK)
- products → product_categories (FK)

### Performance Indexes
- demand: demand_date, warehouse_id, product_id, status
- dispatch: dispatch_date, demand_id
- stock_transactions: warehouse_id, product_id, transaction_type

---

## D. Business Logic

### Automatic Calculations
- **Remaining** = Demand Quantity - SUM(Dispatched Quantities)
- **Delivery %** = Delivered / Demand × 100
- **Current Stock** = SUM(opening + received + adjustment) - SUM(dispatched)
- **Stock Status**: Green (> Buffer), Yellow (≤ Buffer), Red (≤ Minimum)
- **Stock Sufficiency**: Current Stock vs Pending Demand

### Alert Rules
- 🚨 LOW STOCK: Current Stock ≤ Minimum Stock
- ⚠️ HIGH PENDING: Delivery % < 50% of demand
- 🔴 INSUFFICIENT: Current stock cannot fulfil pending demand

---

## E. Features Implemented (v1.0)

✅ Dashboard with 6 KPI cards
✅ Sidebar filters (warehouse, product, category, date range)
✅ Year-on-Year comparison
✅ Demand vs Delivered bar charts
✅ Stock by Product charts
✅ Color-coded status indicators (green/yellow/red)
✅ Demand management (add, view, edit, search)
✅ Dispatch management linked to demand
✅ Automatic stock deduction on dispatch
✅ Stock transactions (opening, received, adjustment)
✅ Stock sufficiency analysis
✅ Product master with categories
✅ Warehouse master with quick-add for Pakistan cities
✅ 7 report types with Excel export
✅ Excel import with preview and validation
✅ Downloadable import templates
✅ Bilingual labels (English + Urdu)
✅ Database backup & restore
✅ Audit logging
✅ Professional CSS styling
✅ Search functionality

---

## F. Development Roadmap — Next Sessions

### Session 2 (Planned)
- [ ] Login/authentication system with session management
- [ ] Role-based access (admin vs user)
- [ ] Monthly demand trend line chart on dashboard
- [ ] Warehouse-wise demand distribution pie chart
- [ ] Demand entry from Excel (batch upload improvements)

### Session 3 (Planned)
- [ ] Purchase Order management module
- [ ] Supplier management
- [ ] Print-ready report PDFs
- [ ] Email alerts for low stock

### Session 4 (Planned)
- [ ] Dashboard auto-refresh
- [ ] Advanced analytics (demand forecasting)
- [ ] Multi-language full Urdu UI
- [ ] Mobile-responsive optimizations

### Future (v2.0)
- [ ] Multi-user with proper RBAC
- [ ] PostgreSQL migration for scalability
- [ ] REST API layer
- [ ] Docker containerization
- [ ] Cloud deployment (Railway/Render)
