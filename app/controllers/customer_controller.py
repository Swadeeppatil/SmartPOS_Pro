"""
SmartPOS Pro - Customer Controller
"""
import logging
from datetime import datetime
from app.models.database import DatabaseManager

logger = logging.getLogger(__name__)


class CustomerController:
    def __init__(self):
        self.db = DatabaseManager()

    def add_customer(self, data: dict):
        if not data.get("name"):
            return {"success": False, "message": "Customer name required."}
        try:
            cid = self.db.execute(
                """INSERT INTO customers
                   (name, phone, email, address, city, state, pincode,
                    date_of_birth, gst_number, membership_type, credit_limit)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (data["name"], data.get("phone"), data.get("email"),
                 data.get("address"), data.get("city"), data.get("state"),
                 data.get("pincode"), data.get("date_of_birth"),
                 data.get("gst_number"), data.get("membership_type", "regular"),
                 float(data.get("credit_limit", 0)))
            )
            return {"success": True, "customer_id": cid}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def update_customer(self, cid: int, data: dict):
        self.db.execute(
            """UPDATE customers SET name=?,phone=?,email=?,address=?,
               city=?,state=?,membership_type=?,credit_limit=?,updated_at=?
               WHERE id=?""",
            (data["name"], data.get("phone"), data.get("email"),
             data.get("address"), data.get("city"), data.get("state"),
             data.get("membership_type","regular"),
             float(data.get("credit_limit",0)),
             datetime.now().isoformat(), cid)
        )
        return {"success": True}

    def delete_customer(self, cid: int):
        self.db.execute(
            "UPDATE customers SET is_active=0 WHERE id=?", (cid,))
        return {"success": True}

    def get_customer(self, cid: int):
        return self.db.fetchone(
            "SELECT * FROM customers WHERE id=?", (cid,))

    def get_all_customers(self, search=None):
        if search:
            term = f"%{search}%"
            return self.db.fetchall(
                """SELECT * FROM customers WHERE is_active=1
                   AND (name LIKE ? OR phone LIKE ? OR email LIKE ?)
                   ORDER BY name""",
                (term, term, term))
        return self.db.fetchall(
            "SELECT * FROM customers WHERE is_active=1 ORDER BY name")

    def get_customer_purchase_history(self, cid: int, limit=50):
        return self.db.fetchall(
            """SELECT i.*, COUNT(ii.id) as item_count
               FROM invoices i
               LEFT JOIN invoice_items ii ON i.id=ii.invoice_id
               WHERE i.customer_id=?
               GROUP BY i.id ORDER BY i.invoice_date DESC LIMIT ?""",
            (cid, limit))

    def get_top_customers(self, limit=10):
        return self.db.fetchall(
            """SELECT c.id, c.name, c.phone,
               COUNT(i.id) as total_orders,
               SUM(i.total_amount) as total_spent
               FROM customers c
               LEFT JOIN invoices i ON c.id=i.customer_id
               GROUP BY c.id ORDER BY total_spent DESC LIMIT ?""",
            (limit,))

    def add_reward_points(self, cid: int, points: int):
        self.db.execute(
            "UPDATE customers SET reward_points=reward_points+? WHERE id=?",
            (points, cid))
        return {"success": True}

    def redeem_reward_points(self, cid: int, points: int):
        customer = self.get_customer(cid)
        if not customer:
            return {"success": False, "message": "Customer not found."}
        if customer["reward_points"] < points:
            return {"success": False, "message": "Insufficient reward points."}
        self.db.execute(
            "UPDATE customers SET reward_points=reward_points-? WHERE id=?",
            (points, cid))
        return {"success": True, "discount_value": points * 0.1}


class SupplierController:
    def __init__(self):
        self.db = DatabaseManager()

    def add_supplier(self, data: dict):
        if not data.get("name"):
            return {"success": False, "message": "Supplier name required."}
        try:
            sid = self.db.execute(
                """INSERT INTO suppliers
                   (name, contact_person, phone, email, address,
                    city, state, gst_number, credit_limit)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (data["name"], data.get("contact_person"), data.get("phone"),
                 data.get("email"), data.get("address"), data.get("city"),
                 data.get("state"), data.get("gst_number"),
                 float(data.get("credit_limit", 0)))
            )
            return {"success": True, "supplier_id": sid}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def update_supplier(self, sid: int, data: dict):
        self.db.execute(
            """UPDATE suppliers SET name=?,contact_person=?,phone=?,email=?,
               address=?,city=?,state=?,gst_number=?,updated_at=? WHERE id=?""",
            (data["name"], data.get("contact_person"), data.get("phone"),
             data.get("email"), data.get("address"), data.get("city"),
             data.get("state"), data.get("gst_number"),
             datetime.now().isoformat(), sid)
        )
        return {"success": True}

    def delete_supplier(self, sid: int):
        self.db.execute(
            "UPDATE suppliers SET is_active=0 WHERE id=?", (sid,))
        return {"success": True}

    def get_all_suppliers(self, search=None):
        if search:
            term = f"%{search}%"
            return self.db.fetchall(
                """SELECT * FROM suppliers WHERE is_active=1
                   AND (name LIKE ? OR phone LIKE ? OR gst_number LIKE ?)
                   ORDER BY name""",
                (term, term, term))
        return self.db.fetchall(
            "SELECT * FROM suppliers WHERE is_active=1 ORDER BY name")

    def get_supplier(self, sid: int):
        return self.db.fetchone(
            "SELECT * FROM suppliers WHERE id=?", (sid,))

    def create_purchase_order(self, data: dict, items: list, user_id: int):
        """Create a purchase order for a supplier."""
        po_number = self._generate_po_number()
        subtotal = sum(i["quantity"] * i["unit_price"] for i in items)

        po_id = self.db.execute(
            """INSERT INTO purchase_orders
               (po_number, supplier_id, user_id, expected_date, subtotal, total_amount)
               VALUES (?,?,?,?,?,?)""",
            (po_number, data["supplier_id"], user_id,
             data.get("expected_date"), subtotal, subtotal)
        )
        for item in items:
            self.db.execute(
                """INSERT INTO purchase_order_items
                   (po_id, product_id, quantity, unit_price, total_price)
                   VALUES (?,?,?,?,?)""",
                (po_id, item["product_id"], item["quantity"],
                 item["unit_price"], item["quantity"] * item["unit_price"])
            )
        return {"success": True, "po_id": po_id, "po_number": po_number}

    def get_purchase_orders(self, supplier_id=None, status=None):
        conditions = ["1=1"]
        params = []
        if supplier_id:
            conditions.append("po.supplier_id=?")
            params.append(supplier_id)
        if status:
            conditions.append("po.status=?")
            params.append(status)
        where = " AND ".join(conditions)
        return self.db.fetchall(
            f"""SELECT po.*, s.name as supplier_name
                FROM purchase_orders po
                LEFT JOIN suppliers s ON po.supplier_id=s.id
                WHERE {where} ORDER BY po.order_date DESC""",
            params)

    def receive_purchase_order(self, po_id: int, user_id: int):
        """Mark PO as received and update inventory."""
        items = self.db.fetchall(
            "SELECT * FROM purchase_order_items WHERE po_id=?", (po_id,))
        from app.controllers.product_controller import ProductController
        pc = ProductController()
        for item in items:
            pc.update_stock(
                item["product_id"], item["quantity"],
                "purchase", f"PO #{po_id} received", user_id
            )
        self.db.execute(
            "UPDATE purchase_orders SET status='received', received_date=? WHERE id=?",
            (datetime.now().isoformat(), po_id)
        )
        return {"success": True}

    def _generate_po_number(self):
        last = self.db.fetchone(
            "SELECT po_number FROM purchase_orders ORDER BY id DESC LIMIT 1")
        if last:
            try:
                num = int(last["po_number"].replace("PO", "")) + 1
            except ValueError:
                num = 1001
        else:
            num = 1001
        return f"PO{num:05d}"

