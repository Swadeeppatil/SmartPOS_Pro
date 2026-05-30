"""
SmartPOS Pro - Billing / POS Controller
Full billing engine: cart, discounts, taxes, payments, invoice PDF generation.
"""

import logging
import os
from datetime import datetime, timedelta
from app.models.database import DatabaseManager
from app.controllers.product_controller import ProductController

logger = logging.getLogger(__name__)


class BillingController:
    """POS billing engine with cart, invoicing, and payment processing."""

    def __init__(self):
        self.db = DatabaseManager()
        self.product_ctrl = ProductController()
        self.cart = []
        self.current_customer = None
        self.coupon_applied = None

    # ------------------------------------------------------------------
    # Cart Management
    # ------------------------------------------------------------------

    def add_to_cart(self, product_id=None, barcode=None, quantity=1):
        """Add a product to cart by ID or barcode."""
        if barcode:
            product = self.product_ctrl.get_product_by_barcode(barcode)
        elif product_id:
            product = self.product_ctrl.get_product(product_id)
        else:
            return {"success": False, "message": "Product ID or barcode required."}

        if not product:
            return {"success": False, "message": "Product not found."}

        if product["quantity"] < quantity:
            return {"success": False,
                    "message": f"Insufficient stock. Available: {product['quantity']}"}

        # Check if already in cart
        for item in self.cart:
            if item["product_id"] == product["id"]:
                new_qty = item["quantity"] + quantity
                if product["quantity"] < new_qty:
                    return {"success": False,
                            "message": f"Insufficient stock. Available: {product['quantity']}"}
                item["quantity"] = new_qty
                item["total_price"] = self._calculate_item_total(item)
                return {"success": True, "message": "Cart updated.", "cart": self.get_cart_summary()}

        # Calculate prices
        price = float(product["selling_price"])
        discount = float(product.get("discount", 0))
        gst_rate = float(product.get("gst_rate", 0))
        discounted_price = price * (1 - discount / 100)
        gst_amount = discounted_price * quantity * (gst_rate / 100)
        total = discounted_price * quantity + gst_amount

        cart_item = {
            "product_id": product["id"],
            "product_name": product["name"],
            "barcode": product.get("barcode", ""),
            "unit_price": price,
            "discount": discount,
            "gst_rate": gst_rate,
            "gst_amount": round(gst_amount, 2),
            "quantity": quantity,
            "total_price": round(total, 2),
        }
        self.cart.append(cart_item)
        return {"success": True, "message": "Added to cart.", "cart": self.get_cart_summary()}

    def update_cart_quantity(self, product_id: int, quantity: int):
        """Update quantity of an item in cart."""
        product = self.product_ctrl.get_product(product_id)
        if product and product["quantity"] < quantity:
            return {"success": False,
                    "message": f"Only {product['quantity']} in stock."}

        for item in self.cart:
            if item["product_id"] == product_id:
                if quantity <= 0:
                    return self.remove_from_cart(product_id)
                item["quantity"] = quantity
                item["total_price"] = self._calculate_item_total(item)
                return {"success": True, "cart": self.get_cart_summary()}

        return {"success": False, "message": "Item not in cart."}

    def remove_from_cart(self, product_id: int):
        """Remove an item from the cart."""
        self.cart = [i for i in self.cart if i["product_id"] != product_id]
        return {"success": True, "cart": self.get_cart_summary()}

    def clear_cart(self):
        """Clear the entire cart."""
        self.cart = []
        self.current_customer = None
        self.coupon_applied = None
        return {"success": True}

    def set_customer(self, customer_id: int):
        """Associate a customer with the current sale."""
        customer = self.db.fetchone(
            "SELECT * FROM customers WHERE id=?", (customer_id,))
        if customer:
            self.current_customer = dict(customer)
            return {"success": True, "customer": self.current_customer}
        return {"success": False, "message": "Customer not found."}

    def apply_coupon(self, code: str):
        """Validate and apply a coupon code."""
        coupon = self.db.fetchone(
            """SELECT * FROM coupons
               WHERE code=? AND is_active=1
               AND (valid_from IS NULL OR valid_from <= ?)
               AND (valid_until IS NULL OR valid_until >= ?)""",
            (code.upper(), datetime.now().isoformat(), datetime.now().isoformat())
        )
        if not coupon:
            return {"success": False, "message": "Invalid or expired coupon."}

        if coupon["usage_limit"] > 0 and coupon["used_count"] >= coupon["usage_limit"]:
            return {"success": False, "message": "Coupon usage limit reached."}

        summary = self.get_cart_summary()
        if summary["subtotal"] < float(coupon.get("min_purchase", 0)):
            return {
                "success": False,
                "message": f"Minimum purchase ₹{coupon['min_purchase']} required."
            }

        self.coupon_applied = dict(coupon)
        return {"success": True, "coupon": self.coupon_applied,
                "cart": self.get_cart_summary()}

    def get_cart_summary(self):
        """Calculate and return full cart summary."""
        subtotal = sum(i["unit_price"] * (1 - i["discount"] / 100) * i["quantity"]
                       for i in self.cart)
        total_gst = sum(i["gst_amount"] for i in self.cart)
        coupon_discount = 0

        if self.coupon_applied:
            cp = self.coupon_applied
            if cp["discount_type"] == "percentage":
                coupon_discount = subtotal * cp["discount_value"] / 100
                if cp.get("max_discount", 0) > 0:
                    coupon_discount = min(coupon_discount, cp["max_discount"])
            else:
                coupon_discount = float(cp["discount_value"])

        total = subtotal + total_gst - coupon_discount

        return {
            "items": self.cart,
            "item_count": len(self.cart),
            "subtotal": round(subtotal, 2),
            "total_gst": round(total_gst, 2),
            "coupon_discount": round(coupon_discount, 2),
            "total": round(total, 2),
            "customer": self.current_customer,
            "coupon": self.coupon_applied,
        }

    # ------------------------------------------------------------------
    # Invoice Processing
    # ------------------------------------------------------------------

    def create_invoice(self, payment_data: dict, user_id: int):
        """
        Finalize sale: create invoice, deduct stock, update customer.
        payment_data: {method, paid_amount, split_payments=[]}
        """
        if not self.cart:
            return {"success": False, "message": "Cart is empty."}

        summary = self.get_cart_summary()
        total = summary["total"]
        paid = float(payment_data.get("paid_amount", total))
        balance = round(total - paid, 2)

        payment_status = "paid" if balance <= 0 else "partial"
        invoice_number = self._generate_invoice_number()

        try:
            # Create invoice record
            invoice_id = self.db.execute(
                """INSERT INTO invoices
                   (invoice_number, customer_id, user_id, subtotal,
                    discount_amount, tax_amount, total_amount,
                    paid_amount, balance, payment_method, payment_status,
                    coupon_code, coupon_discount)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    invoice_number,
                    self.current_customer["id"] if self.current_customer else None,
                    user_id,
                    summary["subtotal"],
                    0,
                    summary["total_gst"],
                    total, paid, balance,
                    payment_data.get("method", "cash"),
                    payment_status,
                    self.coupon_applied["code"] if self.coupon_applied else None,
                    summary["coupon_discount"]
                )
            )

            # Add invoice items and deduct stock
            for item in self.cart:
                self.db.execute(
                    """INSERT INTO invoice_items
                       (invoice_id, product_id, product_name, barcode,
                        quantity, unit_price, discount, gst_rate,
                        gst_amount, total_price)
                       VALUES (?,?,?,?,?,?,?,?,?,?)""",
                    (
                        invoice_id, item["product_id"], item["product_name"],
                        item.get("barcode"), item["quantity"],
                        item["unit_price"], item["discount"],
                        item["gst_rate"], item["gst_amount"], item["total_price"]
                    )
                )
                # Deduct stock
                self.product_ctrl.update_stock(
                    item["product_id"], -item["quantity"],
                    "sale", f"Invoice #{invoice_number}", user_id
                )

            # Record payment
            self.db.execute(
                """INSERT INTO payments
                   (invoice_id, amount, method, user_id)
                   VALUES (?,?,?,?)""",
                (invoice_id, paid, payment_data.get("method", "cash"), user_id)
            )

            # Update coupon usage
            if self.coupon_applied:
                self.db.execute(
                    "UPDATE coupons SET used_count=used_count+1 WHERE id=?",
                    (self.coupon_applied["id"],)
                )

            # Update customer stats
            if self.current_customer:
                points_earned = int(total // 100)
                self.db.execute(
                    """UPDATE customers SET
                       total_purchases=total_purchases+?,
                       reward_points=reward_points+?,
                       updated_at=?
                       WHERE id=?""",
                    (total, points_earned, datetime.now().isoformat(),
                     self.current_customer["id"])
                )

            logger.info(f"Invoice #{invoice_number} created (ID: {invoice_id})")
            self.clear_cart()

            return {
                "success": True,
                "invoice_id": invoice_id,
                "invoice_number": invoice_number,
                "total": total,
                "balance": balance,
                "message": "Invoice created successfully."
            }

        except Exception as e:
            logger.error(f"Invoice creation error: {e}")
            return {"success": False, "message": str(e)}

    def get_invoice(self, invoice_id: int):
        """Get full invoice details including items."""
        invoice = self.db.fetchone(
            """SELECT i.*, c.name as customer_name, c.phone as customer_phone,
               u.full_name as cashier_name
               FROM invoices i
               LEFT JOIN customers c ON i.customer_id=c.id
               LEFT JOIN users u ON i.user_id=u.id
               WHERE i.id=?""",
            (invoice_id,)
        )
        if not invoice:
            return None

        items = self.db.fetchall(
            "SELECT * FROM invoice_items WHERE invoice_id=?", (invoice_id,))
        invoice["items"] = items
        return invoice

    def get_invoices(self, date_from=None, date_to=None,
                     customer_id=None, status=None, limit=100):
        """Retrieve invoices with filters."""
        conditions = ["1=1"]
        params = []

        if date_from:
            conditions.append("DATE(i.invoice_date) >= ?")
            params.append(date_from)
        if date_to:
            conditions.append("DATE(i.invoice_date) <= ?")
            params.append(date_to)
        if customer_id:
            conditions.append("i.customer_id=?")
            params.append(customer_id)
        if status:
            conditions.append("i.payment_status=?")
            params.append(status)

        where = " AND ".join(conditions)
        return self.db.fetchall(
            f"""SELECT i.*, c.name as customer_name, u.full_name as cashier_name
                FROM invoices i
                LEFT JOIN customers c ON i.customer_id=c.id
                LEFT JOIN users u ON i.user_id=u.id
                WHERE {where}
                ORDER BY i.invoice_date DESC LIMIT ?""",
            params + [limit]
        )

    def process_return(self, invoice_id: int, items_to_return: list, user_id: int):
        """Process a sales return for specific items."""
        invoice = self.get_invoice(invoice_id)
        if not invoice:
            return {"success": False, "message": "Invoice not found."}

        refund_total = 0
        for item_data in items_to_return:
            product_id = item_data["product_id"]
            qty = item_data["quantity"]
            price = item_data["unit_price"]
            refund_total += qty * price

            # Return stock
            self.product_ctrl.update_stock(
                product_id, qty, "return",
                f"Return from Invoice #{invoice['invoice_number']}", user_id
            )

        # Mark invoice as returned
        self.db.execute(
            "UPDATE invoices SET is_returned=1 WHERE id=?", (invoice_id,))

        return {
            "success": True,
            "refund_amount": round(refund_total, 2),
            "message": "Return processed successfully."
        }

    # ------------------------------------------------------------------
    # PDF Invoice Generation
    # ------------------------------------------------------------------

    def generate_invoice_pdf(self, invoice_id: int, output_path: str = None):
        """Generate a PDF invoice using ReportLab."""
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib import colors
            from reportlab.lib.units import mm
            from reportlab.platypus import (
                SimpleDocTemplate, Table, TableStyle,
                Paragraph, Spacer, HRFlowable
            )
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT

            invoice = self.get_invoice(invoice_id)
            if not invoice:
                return {"success": False, "message": "Invoice not found."}

            if not output_path:
                os.makedirs("assets/invoices", exist_ok=True)
                output_path = f"assets/invoices/invoice_{invoice['invoice_number']}.pdf"

            doc = SimpleDocTemplate(output_path, pagesize=A4,
                                    topMargin=10*mm, bottomMargin=10*mm,
                                    leftMargin=15*mm, rightMargin=15*mm)

            styles = getSampleStyleSheet()
            story = []

            # Company header
            header_style = ParagraphStyle(
                "Header", fontSize=22, fontName="Helvetica-Bold",
                textColor=colors.HexColor("#2D3748"), alignment=TA_CENTER
            )
            sub_style = ParagraphStyle(
                "Sub", fontSize=9, fontName="Helvetica",
                textColor=colors.HexColor("#718096"), alignment=TA_CENTER
            )
            story.append(Paragraph("SmartPOS Pro", header_style))
            story.append(Paragraph("Smart Inventory & Billing System", sub_style))
            story.append(Spacer(1, 5*mm))
            story.append(HRFlowable(width="100%", thickness=2,
                                    color=colors.HexColor("#4299E1")))
            story.append(Spacer(1, 3*mm))

            # Invoice meta
            meta_data = [
                ["Invoice #:", invoice["invoice_number"],
                 "Date:", invoice["invoice_date"][:10]],
                ["Customer:", invoice.get("customer_name", "Walk-in Customer"),
                 "Cashier:", invoice.get("cashier_name", "")],
                ["Payment:", invoice["payment_method"].upper(),
                 "Status:", invoice["payment_status"].upper()],
            ]
            meta_table = Table(meta_data, colWidths=[30*mm, 65*mm, 25*mm, 55*mm])
            meta_table.setStyle(TableStyle([
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
                ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#4299E1")),
                ("TEXTCOLOR", (2, 0), (2, -1), colors.HexColor("#4299E1")),
            ]))
            story.append(meta_table)
            story.append(Spacer(1, 5*mm))

            # Items table
            items_header = ["#", "Product", "Qty", "Rate", "GST%", "Amount"]
            items_data = [items_header]
            for i, item in enumerate(invoice["items"], 1):
                items_data.append([
                    str(i),
                    item["product_name"],
                    str(item["quantity"]),
                    f"₹{item['unit_price']:.2f}",
                    f"{item['gst_rate']}%",
                    f"₹{item['total_price']:.2f}"
                ])

            col_widths = [10*mm, 75*mm, 15*mm, 25*mm, 20*mm, 30*mm]
            items_table = Table(items_data, colWidths=col_widths)
            items_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4299E1")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1),
                 [colors.white, colors.HexColor("#EBF8FF")]),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#BEE3F8")),
                ("ALIGN", (2, 0), (-1, -1), "CENTER"),
                ("ALIGN", (5, 0), (5, -1), "RIGHT"),
            ]))
            story.append(items_table)
            story.append(Spacer(1, 5*mm))

            # Totals
            totals = [
                ["", "Subtotal:", f"₹{invoice['subtotal']:.2f}"],
                ["", "GST:", f"₹{invoice['tax_amount']:.2f}"],
            ]
            if invoice.get("coupon_discount", 0) > 0:
                totals.append(
                    ["", f"Coupon ({invoice.get('coupon_code', '')}):",
                     f"-₹{invoice['coupon_discount']:.2f}"]
                )
            totals.append(
                ["", "TOTAL:", f"₹{invoice['total_amount']:.2f}"])
            totals.append(
                ["", "Paid:", f"₹{invoice['paid_amount']:.2f}"])
            if float(invoice.get("balance", 0)) > 0:
                totals.append(
                    ["", "Balance Due:", f"₹{invoice['balance']:.2f}"])

            totals_table = Table(totals, colWidths=[100*mm, 40*mm, 35*mm])
            totals_table.setStyle(TableStyle([
                ("FONTNAME", (1, 0), (1, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ALIGN", (2, 0), (2, -1), "RIGHT"),
                ("FONTNAME", (1, -2), (2, -2), "Helvetica-Bold"),
                ("FONTSIZE", (1, -2), (2, -2), 12),
                ("TEXTCOLOR", (1, -2), (2, -2), colors.HexColor("#2D3748")),
                ("LINEABOVE", (1, -2), (2, -2), 1.5, colors.HexColor("#4299E1")),
            ]))
            story.append(totals_table)
            story.append(Spacer(1, 5*mm))
            story.append(HRFlowable(width="100%", thickness=1,
                                    color=colors.HexColor("#E2E8F0")))

            footer_style = ParagraphStyle(
                "Footer", fontSize=8, fontName="Helvetica",
                textColor=colors.HexColor("#A0AEC0"), alignment=TA_CENTER
            )
            story.append(Paragraph(
                "Thank you for your business! | SmartPOS Pro",
                footer_style
            ))

            doc.build(story)
            return {"success": True, "path": output_path}

        except ImportError:
            return {"success": False, "message": "ReportLab not installed."}
        except Exception as e:
            logger.error(f"PDF generation error: {e}")
            return {"success": False, "message": str(e)}

    # ------------------------------------------------------------------
    # Sales Analytics
    # ------------------------------------------------------------------

    def get_sales_summary(self, period="today"):
        """Return sales totals for given period."""
        now = datetime.now()
        if period == "today":
            date_from = now.strftime("%Y-%m-%d")
            date_to = date_from
        elif period == "week":
            date_from = (now - timedelta(days=7)).strftime("%Y-%m-%d")
            date_to = now.strftime("%Y-%m-%d")
        elif period == "month":
            date_from = now.strftime("%Y-%m-01")
            date_to = now.strftime("%Y-%m-%d")
        elif period == "year":
            date_from = now.strftime("%Y-01-01")
            date_to = now.strftime("%Y-%m-%d")
        else:
            date_from = date_to = now.strftime("%Y-%m-%d")

        return self.db.fetchone(
            """SELECT
               COUNT(*) as total_orders,
               SUM(total_amount) as total_revenue,
               SUM(total_amount - tax_amount) as net_sales,
               SUM(tax_amount) as total_tax,
               AVG(total_amount) as avg_order_value
               FROM invoices
               WHERE DATE(invoice_date) BETWEEN ? AND ?
               AND payment_status != 'cancelled'""",
            (date_from, date_to)
        ) or {}

    def get_daily_sales_trend(self, days=30):
        """Get daily sales for the last N days."""
        return self.db.fetchall(
            """SELECT DATE(invoice_date) as date,
               COUNT(*) as orders,
               SUM(total_amount) as revenue
               FROM invoices
               WHERE DATE(invoice_date) >= DATE('now', ?)
               GROUP BY DATE(invoice_date)
               ORDER BY date""",
            (f"-{days} days",)
        )

    def get_top_products(self, limit=10, days=30):
        """Get best-selling products by revenue."""
        return self.db.fetchall(
            """SELECT ii.product_name, SUM(ii.quantity) as total_qty,
               SUM(ii.total_price) as total_revenue
               FROM invoice_items ii
               JOIN invoices i ON ii.invoice_id=i.id
               WHERE DATE(i.invoice_date) >= DATE('now', ?)
               GROUP BY ii.product_id
               ORDER BY total_revenue DESC LIMIT ?""",
            (f"-{days} days", limit)
        )

    def _calculate_item_total(self, item: dict):
        price = item["unit_price"] * (1 - item["discount"] / 100)
        gst = price * item["quantity"] * (item["gst_rate"] / 100)
        item["gst_amount"] = round(gst, 2)
        return round(price * item["quantity"] + gst, 2)

    def _generate_invoice_number(self):
        """Generate sequential invoice number."""
        last = self.db.fetchone(
            "SELECT invoice_number FROM invoices ORDER BY id DESC LIMIT 1")
        if last:
            try:
                num = int(last["invoice_number"].replace("INV", "")) + 1
            except ValueError:
                num = 10001
        else:
            num = 10001
        return f"INV{num:06d}"

