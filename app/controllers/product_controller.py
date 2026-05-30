"""
SmartPOS Pro - Product Controller
Full CRUD for products, barcode generation, CSV/Excel import.
"""

import csv
import os
import logging
import barcode as python_barcode
from barcode.writer import ImageWriter
from datetime import datetime
from app.models.database import DatabaseManager
import qrcode
import io

logger = logging.getLogger(__name__)


class ProductController:
    """Handles all product-related business logic."""

    def __init__(self):
        self.db = DatabaseManager()

    # ------------------------------------------------------------------
    # CRUD Operations
    # ------------------------------------------------------------------

    def add_product(self, data: dict):
        """Add a new product to the database."""
        required = ["name", "selling_price"]
        for f in required:
            if data.get(f) is None or str(data.get(f, "")).strip() == "":
                return {"success": False, "message": f"{f} is required."}

        # Auto-generate product code if not provided
        if not data.get("product_code"):
            data["product_code"] = self._generate_product_code()

        # Dynamic Barcode Generation if not provided
        if not data.get("barcode"):
            import random
            data["barcode"] = f"890{random.randint(100000000, 999999999)}"

        # Expiry date validation (cannot be in the past)
        expiry = data.get("expiry_date")
        if expiry and str(expiry).strip():
            try:
                # Try parsing standard YYYY-MM-DD
                exp_date = datetime.strptime(str(expiry).strip(), "%Y-%m-%d").date()
                if exp_date < datetime.now().date():
                    return {"success": False, "message": "Expiry date cannot be a past date."}
            except ValueError:
                return {"success": False, "message": "Expiry date must be in YYYY-MM-DD format."}

        # Check unique constraints
        if data.get("sku"):
            exists = self.db.fetchone(
                "SELECT id FROM products WHERE sku=?", (data["sku"],))
            if exists:
                return {"success": False, "message": "SKU already exists."}

        try:
            product_id = self.db.execute(
                """INSERT INTO products
                   (name, product_code, sku, barcode, qr_code, image_path,
                    category_id, sub_category_id, brand, supplier_id,
                    description, purchase_price, selling_price, mrp,
                    gst_rate, discount, quantity, min_stock, max_stock, unit,
                    location, expiry_date)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    data["name"], data.get("product_code"), data.get("sku"),
                    data.get("barcode"), data.get("qr_code"),
                    data.get("image_path"), data.get("category_id"),
                    data.get("sub_category_id"), data.get("brand"),
                    data.get("supplier_id"), data.get("description"),
                    float(data.get("purchase_price", 0)),
                    float(data["selling_price"]),
                    float(data.get("mrp", data["selling_price"])),
                    float(data.get("gst_rate", 0)),
                    float(data.get("discount", 0)),
                    int(data.get("quantity", 0)),
                    int(data.get("min_stock", 5)),
                    int(data.get("max_stock", 1000)),
                    data.get("unit", "pcs"),
                    data.get("location"), data.get("expiry_date")
                )
            )
            # Log inventory transaction
            if int(data.get("quantity", 0)) > 0:
                self.db.execute(
                    """INSERT INTO inventory_transactions
                       (product_id, transaction_type, quantity,
                        quantity_before, quantity_after, notes)
                       VALUES (?,?,?,?,?,?)""",
                    (product_id, "opening_stock",
                     int(data.get("quantity", 0)), 0,
                     int(data.get("quantity", 0)), "Initial stock")
                )
            logger.info(f"Product added: {data['name']} (ID: {product_id})")
            return {"success": True, "message": "Product added.", "product_id": product_id}
        except Exception as e:
            logger.error(f"Add product error: {e}")
            return {"success": False, "message": str(e)}

    def update_product(self, product_id: int, data: dict):
        """Update an existing product."""
        # Expiry date validation (cannot be in the past)
        expiry = data.get("expiry_date")
        if expiry and str(expiry).strip():
            try:
                exp_date = datetime.strptime(str(expiry).strip(), "%Y-%m-%d").date()
                if exp_date < datetime.now().date():
                    return {"success": False, "message": "Expiry date cannot be a past date."}
            except ValueError:
                return {"success": False, "message": "Expiry date must be in YYYY-MM-DD format."}

        try:
            self.db.execute(
                """UPDATE products SET
                   name=?, sku=?, barcode=?, image_path=?,
                   category_id=?, brand=?, supplier_id=?,
                   description=?, purchase_price=?, selling_price=?,
                   mrp=?, gst_rate=?, discount=?, min_stock=?,
                   max_stock=?, unit=?, location=?, expiry_date=?,
                   updated_at=?
                   WHERE id=?""",
                (
                    data["name"], data.get("sku"), data.get("barcode"),
                    data.get("image_path"), data.get("category_id"),
                    data.get("brand"), data.get("supplier_id"),
                    data.get("description"),
                    float(data.get("purchase_price", 0)),
                    float(data["selling_price"]),
                    float(data.get("mrp", data["selling_price"])),
                    float(data.get("gst_rate", 0)),
                    float(data.get("discount", 0)),
                    int(data.get("min_stock", 5)),
                    int(data.get("max_stock", 1000)),
                    data.get("unit", "pcs"),
                    data.get("location"), data.get("expiry_date"),
                    datetime.now().isoformat(), product_id
                )
            )
            return {"success": True, "message": "Product updated."}
        except Exception as e:
            logger.error(f"Update product error: {e}")
            return {"success": False, "message": str(e)}

    def delete_product(self, product_id: int):
        """Soft-delete (archive) a product."""
        self.db.execute(
            "UPDATE products SET is_archived=1, is_active=0 WHERE id=?",
            (product_id,)
        )
        return {"success": True, "message": "Product archived."}

    def restore_product(self, product_id: int):
        """Restore an archived product."""
        self.db.execute(
            "UPDATE products SET is_archived=0, is_active=1 WHERE id=?",
            (product_id,)
        )
        return {"success": True, "message": "Product restored."}

    def get_product(self, product_id: int):
        """Get a single product by ID."""
        return self.db.fetchone(
            """SELECT p.*, c.name as category_name, s.name as supplier_name
               FROM products p
               LEFT JOIN categories c ON p.category_id=c.id
               LEFT JOIN suppliers s ON p.supplier_id=s.id
               WHERE p.id=?""",
            (product_id,)
        )

    def get_all_products(self, include_archived=False, category_id=None,
                         search=None, low_stock_only=False):
        """Retrieve products with optional filters."""
        conditions = ["p.is_active=1"]
        params = []

        if not include_archived:
            conditions.append("p.is_archived=0")
        if category_id:
            conditions.append("p.category_id=?")
            params.append(category_id)
        if search:
            conditions.append(
                "(p.name LIKE ? OR p.barcode LIKE ? OR p.sku LIKE ? OR p.product_code LIKE ?)"
            )
            term = f"%{search}%"
            params.extend([term, term, term, term])
        if low_stock_only:
            conditions.append("p.quantity <= p.min_stock")

        where = " AND ".join(conditions)
        query = f"""
            SELECT p.*, c.name as category_name, s.name as supplier_name
            FROM products p
            LEFT JOIN categories c ON p.category_id=c.id
            LEFT JOIN suppliers s ON p.supplier_id=s.id
            WHERE {where}
            ORDER BY p.name
        """
        return self.db.fetchall(query, params)

    def get_product_by_barcode(self, barcode: str):
        """Look up a product by barcode."""
        return self.db.fetchone(
            """SELECT p.*, c.name as category_name
               FROM products p
               LEFT JOIN categories c ON p.category_id=c.id
               WHERE p.barcode=? AND p.is_active=1""",
            (barcode,)
        )

    def update_stock(self, product_id: int, quantity_change: int,
                     transaction_type: str, notes: str = "", user_id=None):
        """Update product stock and log transaction."""
        product = self.db.fetchone(
            "SELECT quantity FROM products WHERE id=?", (product_id,))
        if not product:
            return {"success": False, "message": "Product not found."}

        old_qty = product["quantity"]
        new_qty = old_qty + quantity_change
        if new_qty < 0:
            return {"success": False, "message": "Insufficient stock."}

        self.db.execute(
            "UPDATE products SET quantity=?, updated_at=? WHERE id=?",
            (new_qty, datetime.now().isoformat(), product_id)
        )
        self.db.execute(
            """INSERT INTO inventory_transactions
               (product_id, transaction_type, quantity,
                quantity_before, quantity_after, notes, user_id)
               VALUES (?,?,?,?,?,?,?)""",
            (product_id, transaction_type, abs(quantity_change),
             old_qty, new_qty, notes, user_id)
        )
        return {"success": True, "new_quantity": new_qty}

    # ------------------------------------------------------------------
    # Barcode & QR Generation
    # ------------------------------------------------------------------

    def generate_barcode(self, product_id: int, barcode_type="code128"):
        """Generate and save a barcode image for a product."""
        product = self.get_product(product_id)
        if not product:
            return {"success": False, "message": "Product not found."}

        barcode_data = product.get("barcode") or product["product_code"]
        save_dir = os.path.join("assets", "barcodes")
        os.makedirs(save_dir, exist_ok=True)
        filepath = os.path.join(save_dir, f"product_{product_id}")

        try:
            if barcode_type == "code128":
                bc = python_barcode.get("code128", barcode_data,
                                        writer=ImageWriter())
            elif barcode_type == "ean13":
                # EAN-13 needs exactly 12 digits
                code = barcode_data.replace("-", "").zfill(12)[:12]
                bc = python_barcode.get("ean13", code, writer=ImageWriter())
            else:
                bc = python_barcode.get("code128", barcode_data,
                                        writer=ImageWriter())

            saved = bc.save(filepath)
            self.db.execute(
                "UPDATE products SET barcode=? WHERE id=?",
                (barcode_data, product_id)
            )
            return {"success": True, "path": saved}
        except Exception as e:
            logger.error(f"Barcode generation error: {e}")
            return {"success": False, "message": str(e)}

    def generate_qr_code(self, product_id: int):
        """Generate a QR code for a product."""
        product = self.get_product(product_id)
        if not product:
            return {"success": False, "message": "Product not found."}

        save_dir = os.path.join("assets", "qrcodes")
        os.makedirs(save_dir, exist_ok=True)
        filepath = os.path.join(save_dir, f"product_{product_id}.png")

        try:
            qr_data = {
                "id": product["id"],
                "name": product["name"],
                "price": product["selling_price"],
                "barcode": product.get("barcode", "")
            }
            import json
            qr = qrcode.QRCode(version=1, box_size=10, border=5)
            qr.add_data(json.dumps(qr_data))
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            img.save(filepath)
            self.db.execute(
                "UPDATE products SET qr_code=? WHERE id=?",
                (filepath, product_id)
            )
            return {"success": True, "path": filepath}
        except Exception as e:
            logger.error(f"QR generation error: {e}")
            return {"success": False, "message": str(e)}

    # ------------------------------------------------------------------
    # Import / Export
    # ------------------------------------------------------------------

    def import_from_csv(self, filepath: str, user_id=None):
        """Bulk import products from a CSV file."""
        results = {"added": 0, "skipped": 0, "errors": []}
        try:
            with open(filepath, newline="", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    result = self.add_product(row)
                    if result["success"]:
                        results["added"] += 1
                    else:
                        results["skipped"] += 1
                        results["errors"].append(
                            f"Row {row.get('name', '?')}: {result['message']}"
                        )
        except Exception as e:
            logger.error(f"CSV import error: {e}")
            results["errors"].append(str(e))
        return results

    def export_to_csv(self, filepath: str):
        """Export all products to CSV."""
        products = self.get_all_products()
        if not products:
            return {"success": False, "message": "No products to export."}

        fieldnames = [
            "id", "name", "product_code", "sku", "barcode", "category_name",
            "brand", "supplier_name", "purchase_price", "selling_price",
            "mrp", "gst_rate", "discount", "quantity", "min_stock",
            "max_stock", "unit"
        ]
        try:
            with open(filepath, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames,
                                       extrasaction="ignore")
                writer.writeheader()
                writer.writerows(products)
            return {"success": True, "message": f"Exported {len(products)} products."}
        except Exception as e:
            return {"success": False, "message": str(e)}

    # ------------------------------------------------------------------
    # Analytics Helpers
    # ------------------------------------------------------------------

    def get_low_stock_products(self):
        """Products at or below min_stock."""
        return self.db.fetchall(
            """SELECT p.*, c.name as category_name
               FROM products p LEFT JOIN categories c ON p.category_id=c.id
               WHERE p.quantity <= p.min_stock AND p.is_active=1 AND p.is_archived=0
               ORDER BY p.quantity ASC"""
        )

    def get_out_of_stock_products(self):
        """Products with zero quantity."""
        return self.db.fetchall(
            """SELECT p.*, c.name as category_name
               FROM products p LEFT JOIN categories c ON p.category_id=c.id
               WHERE p.quantity=0 AND p.is_active=1 AND p.is_archived=0
               ORDER BY p.name"""
        )

    def get_inventory_value(self):
        """Calculate total inventory value."""
        result = self.db.fetchone(
            """SELECT
               SUM(quantity * purchase_price) as purchase_value,
               SUM(quantity * selling_price) as selling_value,
               COUNT(*) as total_products,
               SUM(CASE WHEN quantity=0 THEN 1 ELSE 0 END) as out_of_stock,
               SUM(CASE WHEN quantity<=min_stock AND quantity>0 THEN 1 ELSE 0 END) as low_stock
               FROM products WHERE is_active=1 AND is_archived=0"""
        )
        return result or {}

    def get_categories(self):
        """Get all product categories."""
        return self.db.fetchall("SELECT * FROM categories ORDER BY name")

    def _generate_product_code(self):
        """Auto-generate a unique product code."""
        last = self.db.fetchone(
            "SELECT product_code FROM products ORDER BY id DESC LIMIT 1")
        if last and last["product_code"]:
            try:
                num = int(last["product_code"].replace("PRD", "")) + 1
            except ValueError:
                num = 1001
        else:
            num = 1001
        return f"PRD{num:05d}"

