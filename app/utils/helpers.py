"""
SmartPOS Pro - Utility helpers: logging, backup, notifications, barcode scanner.
"""
import logging
import os
import shutil
import json
from datetime import datetime
from app.models.database import DatabaseManager

logger = logging.getLogger(__name__)


def setup_logging(log_level=logging.DEBUG):
    os.makedirs("logs", exist_ok=True)
    log_file = f"logs/smartpos_{datetime.now().strftime('%Y%m%d')}.log"
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler()
        ]
    )
    logger.info("SmartPOS Pro logging initialized.")


def format_currency(amount, symbol="₹"):
    try:
        return f"{symbol}{float(amount):,.2f}"
    except (TypeError, ValueError):
        return f"{symbol}0.00"


def format_date(dt_str, fmt="%d %b %Y"):
    if not dt_str:
        return ""
    try:
        dt = datetime.fromisoformat(str(dt_str)[:19])
        return dt.strftime(fmt)
    except Exception:
        return str(dt_str)[:10]


def validate_phone(phone: str):
    import re
    cleaned = re.sub(r"\D", "", phone)
    return len(cleaned) >= 10


def validate_email(email: str):
    import re
    pattern = r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
    return re.match(pattern, email) is not None


class BackupManager:
    def __init__(self):
        self.db = DatabaseManager()
        self.backup_dir = "backups"
        os.makedirs(self.backup_dir, exist_ok=True)

    def create_backup(self, backup_type="manual"):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"smartpos_backup_{timestamp}.db"
        dest = os.path.join(self.backup_dir, filename)
        try:
            shutil.copy2(self.db.db_path, dest)
            size = os.path.getsize(dest)
            self.db.execute(
                "INSERT INTO backups (filename, size_bytes, type) VALUES (?,?,?)",
                (filename, size, backup_type)
            )
            logger.info(f"Backup created: {filename}")
            return {"success": True, "filename": filename, "path": dest, "size": size}
        except Exception as e:
            logger.error(f"Backup error: {e}")
            return {"success": False, "message": str(e)}

    def restore_backup(self, backup_path: str):
        try:
            if not os.path.exists(backup_path):
                return {"success": False, "message": "Backup file not found."}
            shutil.copy2(backup_path, self.db.db_path)
            logger.info(f"Database restored from: {backup_path}")
            return {"success": True, "message": "Database restored. Restart the app."}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def list_backups(self):
        return self.db.fetchall(
            "SELECT * FROM backups ORDER BY created_at DESC LIMIT 50")

    def export_data_json(self, output_path: str):
        """Export all key tables as JSON."""
        tables = ["products", "customers", "suppliers",
                  "invoices", "invoice_items", "expenses"]
        export = {}
        for table in tables:
            export[table] = self.db.fetchall(f"SELECT * FROM {table}")
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(export, f, indent=2, default=str)
            return {"success": True, "path": output_path}
        except Exception as e:
            return {"success": False, "message": str(e)}


class NotificationManager:
    def __init__(self):
        self.db = DatabaseManager()

    def send_notification(self, title, message, notif_type="info",
                          user_id=None, related_id=None, related_type=None):
        self.db.execute(
            """INSERT INTO notifications
               (user_id, title, message, type, related_id, related_type)
               VALUES (?,?,?,?,?,?)""",
            (user_id, title, message, notif_type, related_id, related_type)
        )

    def get_notifications(self, user_id=None, unread_only=False, limit=50):
        conditions = ["1=1"]
        params = []
        if user_id:
            conditions.append("(user_id=? OR user_id IS NULL)")
            params.append(user_id)
        if unread_only:
            conditions.append("is_read=0")
        where = " AND ".join(conditions)
        return self.db.fetchall(
            f"""SELECT * FROM notifications WHERE {where}
                ORDER BY created_at DESC LIMIT ?""",
            params + [limit]
        )

    def mark_read(self, notification_id: int):
        self.db.execute(
            "UPDATE notifications SET is_read=1 WHERE id=?", (notification_id,))

    def mark_all_read(self, user_id=None):
        if user_id:
            self.db.execute(
                "UPDATE notifications SET is_read=1 WHERE user_id=?", (user_id,))
        else:
            self.db.execute("UPDATE notifications SET is_read=1")

    def get_unread_count(self, user_id=None):
        if user_id:
            r = self.db.fetchone(
                "SELECT COUNT(*) as cnt FROM notifications WHERE is_read=0 AND (user_id=? OR user_id IS NULL)",
                (user_id,))
        else:
            r = self.db.fetchone(
                "SELECT COUNT(*) as cnt FROM notifications WHERE is_read=0")
        return int(r.get("cnt", 0)) if r else 0

    def check_and_send_stock_alerts(self):
        """Scan for low-stock and send notifications."""
        from app.controllers.product_controller import ProductController
        pc = ProductController()
        low = pc.get_low_stock_products()
        for product in low:
            self.send_notification(
                title="⚠️ Low Stock Alert",
                message=f"{product['name']} has only {product['quantity']} units left.",
                notif_type="warning",
                related_id=product["id"],
                related_type="product"
            )
        out = pc.get_out_of_stock_products()
        for product in out:
            self.send_notification(
                title="🚨 Out of Stock",
                message=f"{product['name']} is out of stock!",
                notif_type="error",
                related_id=product["id"],
                related_type="product"
            )


class BarcodeScanner:
    """Camera-based barcode/QR scanner using OpenCV and pyzbar."""

    def __init__(self, callback=None):
        self.callback = callback
        self.is_scanning = False
        self._cap = None

    def start_scan(self):
        self.is_scanning = True
        try:
            import cv2
            from pyzbar import pyzbar
            self._cap = cv2.VideoCapture(0)
            self._scan_loop()
        except ImportError:
            logger.warning("OpenCV/pyzbar not available. Using manual entry.")
            if self.callback:
                self.callback(None, "manual_entry_required")

    def _scan_loop(self):
        import cv2
        from pyzbar import pyzbar
        while self.is_scanning and self._cap and self._cap.isOpened():
            ret, frame = self._cap.read()
            if not ret:
                break
            codes = pyzbar.decode(frame)
            for code in codes:
                data = code.data.decode("utf-8")
                code_type = code.type
                self.stop_scan()
                if self.callback:
                    self.callback(data, code_type)
                return

    def stop_scan(self):
        self.is_scanning = False
        if self._cap:
            self._cap.release()
            self._cap = None
