"""
SmartPOS Pro - Database Manager
Complete SQLite schema with all tables, indexes, and foreign keys.
"""

import sqlite3
import os
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


def get_db_path():
    """Return platform-appropriate database path."""
    if os.name == "posix" and "ANDROID_ARGUMENT" in os.environ:
        # Android path
        from android.storage import app_storage_path  # type: ignore
        return os.path.join(app_storage_path(), "smartpos.db")
    else:
        base = Path(__file__).resolve().parent.parent.parent
        return str(base / "smartpos.db")


DB_PATH = get_db_path()


class DatabaseManager:
    """Singleton database manager with connection pooling."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.db_path = DB_PATH
        self._create_tables()
        self._seed_defaults()
        logger.info(f"Database initialized at: {self.db_path}")

    def get_connection(self):
        """Return a new SQLite connection with WAL mode enabled."""
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA cache_size=10000")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def execute(self, query, params=()):
        """Execute a single write query."""
        with self.get_connection() as conn:
            cur = conn.execute(query, params)
            conn.commit()
            return cur.lastrowid

    def fetchall(self, query, params=()):
        """Fetch all rows for a SELECT query."""
        with self.get_connection() as conn:
            cur = conn.execute(query, params)
            return [dict(row) for row in cur.fetchall()]

    def fetchone(self, query, params=()):
        """Fetch a single row."""
        with self.get_connection() as conn:
            cur = conn.execute(query, params)
            row = cur.fetchone()
            return dict(row) if row else None

    def _create_tables(self):
        """Create all database tables."""
        with self.get_connection() as conn:
            conn.executescript(SCHEMA_SQL)
            conn.commit()
        logger.info("All tables created/verified.")

    def _seed_defaults(self):
        """Seed default admin user and categories if not present."""
        import hashlib
        existing = self.fetchone("SELECT id FROM users WHERE username='admin'")
        if not existing:
            pwd_hash = hashlib.sha256("admin123".encode()).hexdigest()
            self.execute(
                """INSERT INTO users (username, password_hash, full_name, role, email, is_active)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                ("admin", pwd_hash, "System Administrator", "admin",
                 "admin@smartpos.com", 1)
            )
            logger.info("Default admin user seeded.")

        # Seed default categories
        for cat in ["Electronics", "Groceries", "Clothing", "Medicine",
                    "Beverages", "Snacks", "Household", "Stationery",
                    "Cosmetics", "Other"]:
            exists = self.fetchone(
                "SELECT id FROM categories WHERE name=?", (cat,))
            if not exists:
                self.execute(
                    "INSERT INTO categories (name) VALUES (?)", (cat,))

        # Seed expense categories
        for exp_cat in ["Rent", "Salaries", "Internet", "Electricity",
                        "Water", "Transportation", "Maintenance", "Miscellaneous"]:
            exists = self.fetchone(
                "SELECT id FROM expense_categories WHERE name=?", (exp_cat,))
            if not exists:
                self.execute(
                    "INSERT INTO expense_categories (name) VALUES (?)", (exp_cat,))

        logger.info("Default data seeded.")


# ===========================================================================
# COMPLETE DATABASE SCHEMA
# ===========================================================================

SCHEMA_SQL = """
-- ===========================
-- USERS & AUTHENTICATION
-- ===========================
CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    username        TEXT NOT NULL UNIQUE,
    password_hash   TEXT NOT NULL,
    full_name       TEXT NOT NULL,
    role            TEXT NOT NULL DEFAULT 'cashier',
    email           TEXT,
    phone           TEXT,
    profile_image   TEXT,
    is_active       INTEGER DEFAULT 1,
    failed_attempts INTEGER DEFAULT 0,
    locked_until    TEXT,
    last_login      TEXT,
    remember_token  TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS sessions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    token       TEXT NOT NULL UNIQUE,
    created_at  TEXT DEFAULT (datetime('now')),
    expires_at  TEXT,
    ip_address  TEXT,
    is_active   INTEGER DEFAULT 1,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS activity_logs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER,
    action      TEXT NOT NULL,
    module      TEXT,
    details     TEXT,
    ip_address  TEXT,
    created_at  TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS login_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    login_time  TEXT DEFAULT (datetime('now')),
    logout_time TEXT,
    status      TEXT DEFAULT 'success',
    device_info TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- ===========================
-- CATEGORIES
-- ===========================
CREATE TABLE IF NOT EXISTS categories (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    description TEXT,
    icon        TEXT,
    created_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS sub_categories (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id INTEGER NOT NULL,
    name        TEXT NOT NULL,
    description TEXT,
    created_at  TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE CASCADE
);

-- ===========================
-- SUPPLIERS
-- ===========================
CREATE TABLE IF NOT EXISTS suppliers (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    contact_person  TEXT,
    phone           TEXT,
    email           TEXT,
    address         TEXT,
    city            TEXT,
    state           TEXT,
    gst_number      TEXT,
    pan_number      TEXT,
    bank_name       TEXT,
    bank_account    TEXT,
    ifsc_code       TEXT,
    credit_limit    REAL DEFAULT 0,
    outstanding     REAL DEFAULT 0,
    is_active       INTEGER DEFAULT 1,
    notes           TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now'))
);

-- ===========================
-- PRODUCTS
-- ===========================
CREATE TABLE IF NOT EXISTS products (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    product_code    TEXT UNIQUE,
    sku             TEXT UNIQUE,
    barcode         TEXT,
    qr_code         TEXT,
    image_path      TEXT,
    category_id     INTEGER,
    sub_category_id INTEGER,
    brand           TEXT,
    supplier_id     INTEGER,
    description     TEXT,
    purchase_price  REAL NOT NULL DEFAULT 0,
    selling_price   REAL NOT NULL DEFAULT 0,
    mrp             REAL DEFAULT 0,
    gst_rate        REAL DEFAULT 0,
    discount        REAL DEFAULT 0,
    quantity        INTEGER DEFAULT 0,
    min_stock       INTEGER DEFAULT 5,
    max_stock       INTEGER DEFAULT 1000,
    unit            TEXT DEFAULT 'pcs',
    location        TEXT,
    expiry_date     TEXT,
    is_active       INTEGER DEFAULT 1,
    is_archived     INTEGER DEFAULT 0,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (category_id) REFERENCES categories(id),
    FOREIGN KEY (sub_category_id) REFERENCES sub_categories(id),
    FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
);

CREATE INDEX IF NOT EXISTS idx_products_barcode ON products(barcode);
CREATE INDEX IF NOT EXISTS idx_products_sku ON products(sku);
CREATE INDEX IF NOT EXISTS idx_products_category ON products(category_id);
CREATE INDEX IF NOT EXISTS idx_products_supplier ON products(supplier_id);
CREATE INDEX IF NOT EXISTS idx_products_quantity ON products(quantity);

-- ===========================
-- CUSTOMERS
-- ===========================
CREATE TABLE IF NOT EXISTS customers (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    phone           TEXT,
    email           TEXT,
    address         TEXT,
    city            TEXT,
    state           TEXT,
    pincode         TEXT,
    date_of_birth   TEXT,
    gst_number      TEXT,
    reward_points   INTEGER DEFAULT 0,
    membership_type TEXT DEFAULT 'regular',
    credit_limit    REAL DEFAULT 0,
    outstanding     REAL DEFAULT 0,
    total_purchases REAL DEFAULT 0,
    is_active       INTEGER DEFAULT 1,
    notes           TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_customers_phone ON customers(phone);
CREATE INDEX IF NOT EXISTS idx_customers_name ON customers(name);

-- ===========================
-- INVOICES & SALES
-- ===========================
CREATE TABLE IF NOT EXISTS invoices (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_number  TEXT NOT NULL UNIQUE,
    customer_id     INTEGER,
    user_id         INTEGER NOT NULL,
    invoice_date    TEXT DEFAULT (datetime('now')),
    due_date        TEXT,
    subtotal        REAL NOT NULL DEFAULT 0,
    discount_amount REAL DEFAULT 0,
    tax_amount      REAL DEFAULT 0,
    total_amount    REAL NOT NULL DEFAULT 0,
    paid_amount     REAL DEFAULT 0,
    balance         REAL DEFAULT 0,
    payment_method  TEXT DEFAULT 'cash',
    payment_status  TEXT DEFAULT 'paid',
    coupon_code     TEXT,
    coupon_discount REAL DEFAULT 0,
    notes           TEXT,
    is_returned     INTEGER DEFAULT 0,
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (customer_id) REFERENCES customers(id),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_invoices_date ON invoices(invoice_date);
CREATE INDEX IF NOT EXISTS idx_invoices_customer ON invoices(customer_id);
CREATE INDEX IF NOT EXISTS idx_invoices_status ON invoices(payment_status);

CREATE TABLE IF NOT EXISTS invoice_items (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id      INTEGER NOT NULL,
    product_id      INTEGER NOT NULL,
    product_name    TEXT NOT NULL,
    barcode         TEXT,
    quantity        INTEGER NOT NULL DEFAULT 1,
    unit_price      REAL NOT NULL,
    discount        REAL DEFAULT 0,
    gst_rate        REAL DEFAULT 0,
    gst_amount      REAL DEFAULT 0,
    total_price     REAL NOT NULL,
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (invoice_id) REFERENCES invoices(id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products(id)
);

CREATE INDEX IF NOT EXISTS idx_invoice_items_invoice ON invoice_items(invoice_id);
CREATE INDEX IF NOT EXISTS idx_invoice_items_product ON invoice_items(product_id);

-- ===========================
-- PAYMENTS
-- ===========================
CREATE TABLE IF NOT EXISTS payments (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id      INTEGER NOT NULL,
    payment_date    TEXT DEFAULT (datetime('now')),
    amount          REAL NOT NULL,
    method          TEXT NOT NULL,
    reference_no    TEXT,
    notes           TEXT,
    user_id         INTEGER,
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (invoice_id) REFERENCES invoices(id),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- ===========================
-- INVENTORY
-- ===========================
CREATE TABLE IF NOT EXISTS inventory_transactions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id      INTEGER NOT NULL,
    transaction_type TEXT NOT NULL,
    quantity        INTEGER NOT NULL,
    quantity_before INTEGER,
    quantity_after  INTEGER,
    unit_price      REAL DEFAULT 0,
    total_cost      REAL DEFAULT 0,
    reference_id    INTEGER,
    reference_type  TEXT,
    notes           TEXT,
    user_id         INTEGER,
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (product_id) REFERENCES products(id),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_inv_trans_product ON inventory_transactions(product_id);
CREATE INDEX IF NOT EXISTS idx_inv_trans_type ON inventory_transactions(transaction_type);
CREATE INDEX IF NOT EXISTS idx_inv_trans_date ON inventory_transactions(created_at);

-- ===========================
-- PURCHASE ORDERS
-- ===========================
CREATE TABLE IF NOT EXISTS purchase_orders (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    po_number       TEXT NOT NULL UNIQUE,
    supplier_id     INTEGER NOT NULL,
    user_id         INTEGER NOT NULL,
    order_date      TEXT DEFAULT (datetime('now')),
    expected_date   TEXT,
    received_date   TEXT,
    subtotal        REAL DEFAULT 0,
    tax_amount      REAL DEFAULT 0,
    total_amount    REAL DEFAULT 0,
    paid_amount     REAL DEFAULT 0,
    status          TEXT DEFAULT 'pending',
    notes           TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (supplier_id) REFERENCES suppliers(id),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS purchase_order_items (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    po_id           INTEGER NOT NULL,
    product_id      INTEGER NOT NULL,
    quantity        INTEGER NOT NULL,
    received_qty    INTEGER DEFAULT 0,
    unit_price      REAL NOT NULL,
    total_price     REAL NOT NULL,
    FOREIGN KEY (po_id) REFERENCES purchase_orders(id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products(id)
);

-- ===========================
-- EXPENSES
-- ===========================
CREATE TABLE IF NOT EXISTS expense_categories (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    description TEXT,
    created_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS expenses (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id     INTEGER,
    title           TEXT NOT NULL,
    amount          REAL NOT NULL,
    expense_date    TEXT DEFAULT (datetime('now')),
    payment_method  TEXT DEFAULT 'cash',
    reference_no    TEXT,
    receipt_image   TEXT,
    notes           TEXT,
    user_id         INTEGER,
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (category_id) REFERENCES expense_categories(id),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_expenses_date ON expenses(expense_date);
CREATE INDEX IF NOT EXISTS idx_expenses_category ON expenses(category_id);

-- ===========================
-- EMPLOYEES
-- ===========================
CREATE TABLE IF NOT EXISTS employees (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER,
    emp_code        TEXT UNIQUE,
    full_name       TEXT NOT NULL,
    phone           TEXT,
    email           TEXT,
    address         TEXT,
    department      TEXT,
    designation     TEXT,
    date_of_join    TEXT,
    salary          REAL DEFAULT 0,
    bank_account    TEXT,
    ifsc_code       TEXT,
    is_active       INTEGER DEFAULT 1,
    notes           TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS attendance (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id     INTEGER NOT NULL,
    attendance_date TEXT NOT NULL,
    check_in        TEXT,
    check_out       TEXT,
    status          TEXT DEFAULT 'present',
    hours_worked    REAL DEFAULT 0,
    overtime_hours  REAL DEFAULT 0,
    notes           TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (employee_id) REFERENCES employees(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_attendance_emp ON attendance(employee_id);
CREATE INDEX IF NOT EXISTS idx_attendance_date ON attendance(attendance_date);

CREATE TABLE IF NOT EXISTS payroll (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id     INTEGER NOT NULL,
    month           TEXT NOT NULL,
    basic_salary    REAL DEFAULT 0,
    allowances      REAL DEFAULT 0,
    deductions      REAL DEFAULT 0,
    net_salary      REAL DEFAULT 0,
    payment_date    TEXT,
    payment_method  TEXT DEFAULT 'bank_transfer',
    status          TEXT DEFAULT 'pending',
    notes           TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (employee_id) REFERENCES employees(id)
);

-- ===========================
-- NOTIFICATIONS
-- ===========================
CREATE TABLE IF NOT EXISTS notifications (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER,
    title       TEXT NOT NULL,
    message     TEXT NOT NULL,
    type        TEXT DEFAULT 'info',
    is_read     INTEGER DEFAULT 0,
    related_id  INTEGER,
    related_type TEXT,
    created_at  TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- ===========================
-- COUPONS
-- ===========================
CREATE TABLE IF NOT EXISTS coupons (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    code            TEXT NOT NULL UNIQUE,
    description     TEXT,
    discount_type   TEXT DEFAULT 'percentage',
    discount_value  REAL NOT NULL,
    min_purchase    REAL DEFAULT 0,
    max_discount    REAL DEFAULT 0,
    usage_limit     INTEGER DEFAULT 0,
    used_count      INTEGER DEFAULT 0,
    valid_from      TEXT,
    valid_until     TEXT,
    is_active       INTEGER DEFAULT 1,
    created_at      TEXT DEFAULT (datetime('now'))
);

-- ===========================
-- SETTINGS
-- ===========================
CREATE TABLE IF NOT EXISTS settings (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    key         TEXT NOT NULL UNIQUE,
    value       TEXT,
    type        TEXT DEFAULT 'text',
    description TEXT,
    updated_at  TEXT DEFAULT (datetime('now'))
);

-- ===========================
-- AI PREDICTIONS CACHE
-- ===========================
CREATE TABLE IF NOT EXISTS ai_predictions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    prediction_type TEXT NOT NULL,
    target_date     TEXT NOT NULL,
    predicted_value REAL,
    actual_value    REAL,
    model_version   TEXT,
    confidence      REAL,
    created_at      TEXT DEFAULT (datetime('now'))
);

-- ===========================
-- DATA BACKUPS LOG
-- ===========================
CREATE TABLE IF NOT EXISTS backups (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    filename    TEXT NOT NULL,
    size_bytes  INTEGER,
    type        TEXT DEFAULT 'manual',
    status      TEXT DEFAULT 'success',
    created_at  TEXT DEFAULT (datetime('now'))
);
"""
