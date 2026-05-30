"""
SmartPOS Pro - Analytics & AI Controller
Sales analytics, charts, AI predictions using scikit-learn.
"""
import logging
import os
from datetime import datetime, timedelta
from app.models.database import DatabaseManager
from app.controllers.billing_controller import BillingController

logger = logging.getLogger(__name__)


class AnalyticsController:
    """Advanced analytics and reporting engine."""

    def __init__(self):
        self.db = DatabaseManager()
        self.billing = BillingController()

    def get_dashboard_kpis(self):
        """Return all KPI data for the dashboard."""
        today_sales = self.billing.get_sales_summary("today")
        week_sales = self.billing.get_sales_summary("week")
        month_sales = self.billing.get_sales_summary("month")
        year_sales = self.billing.get_sales_summary("year")

        from app.controllers.product_controller import ProductController
        pc = ProductController()
        inv_value = pc.get_inventory_value()
        low_stock = pc.get_low_stock_products()
        out_of_stock = pc.get_out_of_stock_products()

        total_customers = self.db.fetchone(
            "SELECT COUNT(*) as cnt FROM customers WHERE is_active=1")
        pending_payments = self.db.fetchone(
            """SELECT SUM(balance) as total
               FROM invoices WHERE payment_status='partial' AND balance > 0""")
        total_expenses = self.db.fetchone(
            """SELECT SUM(amount) as total FROM expenses
               WHERE strftime('%Y-%m', expense_date)=strftime('%Y-%m','now')""")

        revenue = float(month_sales.get("total_revenue") or 0)
        expenses = float(total_expenses.get("total") or 0) if total_expenses else 0
        cost = float(self._get_month_cogs() or 0)
        net_profit = revenue - expenses - cost

        return {
            "today_sales": float(today_sales.get("total_revenue") or 0),
            "today_orders": int(today_sales.get("total_orders") or 0),
            "week_sales": float(week_sales.get("total_revenue") or 0),
            "month_sales": float(month_sales.get("total_revenue") or 0),
            "year_sales": float(year_sales.get("total_revenue") or 0),
            "net_profit": round(net_profit, 2),
            "total_products": int(inv_value.get("total_products") or 0),
            "total_customers": int(total_customers.get("cnt") or 0) if total_customers else 0,
            "low_stock_count": len(low_stock),
            "out_of_stock_count": len(out_of_stock),
            "pending_payments": float(pending_payments.get("total") or 0) if pending_payments else 0,
            "monthly_expenses": expenses,
            "inventory_value": float(inv_value.get("selling_value") or 0),
        }

    def _get_month_cogs(self):
        """Cost of Goods Sold for current month."""
        result = self.db.fetchone(
            """SELECT SUM(ii.quantity * p.purchase_price) as cogs
               FROM invoice_items ii
               JOIN invoices i ON ii.invoice_id=i.id
               JOIN products p ON ii.product_id=p.id
               WHERE strftime('%Y-%m', i.invoice_date)=strftime('%Y-%m','now')""")
        return result.get("cogs", 0) if result else 0

    def get_sales_chart_data(self, period="30days"):
        """Return data for sales trend chart."""
        if period == "7days":
            days = 7
        elif period == "30days":
            days = 30
        elif period == "90days":
            days = 90
        else:
            days = 30

        raw = self.billing.get_daily_sales_trend(days)
        dates, revenues, orders = [], [], []
        for row in raw:
            dates.append(row["date"])
            revenues.append(float(row.get("revenue") or 0))
            orders.append(int(row.get("orders") or 0))

        return {"dates": dates, "revenues": revenues, "orders": orders}

    def get_category_sales(self, days=30):
        """Sales breakdown by product category."""
        return self.db.fetchall(
            """SELECT c.name as category,
               SUM(ii.total_price) as revenue,
               SUM(ii.quantity) as qty
               FROM invoice_items ii
               JOIN invoices i ON ii.invoice_id=i.id
               JOIN products p ON ii.product_id=p.id
               LEFT JOIN categories c ON p.category_id=c.id
               WHERE DATE(i.invoice_date) >= DATE('now', ?)
               GROUP BY p.category_id ORDER BY revenue DESC""",
            (f"-{days} days",)
        )

    def get_hourly_sales(self, target_date=None):
        """Sales by hour of day - for peak hours analysis."""
        if not target_date:
            target_date = datetime.now().strftime("%Y-%m-%d")
        return self.db.fetchall(
            """SELECT strftime('%H', invoice_date) as hour,
               COUNT(*) as orders, SUM(total_amount) as revenue
               FROM invoices
               WHERE DATE(invoice_date)=?
               GROUP BY strftime('%H', invoice_date)
               ORDER BY hour""",
            (target_date,)
        )

    def get_profit_margin_by_product(self, limit=20):
        """Calculate profit margins per product."""
        return self.db.fetchall(
            """SELECT p.name,
               SUM(ii.quantity) as units_sold,
               SUM(ii.total_price) as revenue,
               SUM(ii.quantity * p.purchase_price) as cost,
               (SUM(ii.total_price) - SUM(ii.quantity * p.purchase_price)) as profit,
               ROUND(((SUM(ii.total_price) - SUM(ii.quantity * p.purchase_price))
                      / SUM(ii.total_price)) * 100, 2) as margin_pct
               FROM invoice_items ii
               JOIN products p ON ii.product_id=p.id
               GROUP BY ii.product_id
               ORDER BY profit DESC LIMIT ?""",
            (limit,)
        )

    def get_payment_method_breakdown(self, days=30):
        """Revenue by payment method."""
        return self.db.fetchall(
            """SELECT payment_method,
               COUNT(*) as transactions,
               SUM(total_amount) as revenue
               FROM invoices
               WHERE DATE(invoice_date) >= DATE('now', ?)
               GROUP BY payment_method ORDER BY revenue DESC""",
            (f"-{days} days",)
        )

    def generate_report(self, report_type: str, params: dict = None):
        """Generate a comprehensive report."""
        params = params or {}
        if report_type == "sales":
            return self._sales_report(params)
        elif report_type == "inventory":
            return self._inventory_report(params)
        elif report_type == "customer":
            return self._customer_report(params)
        elif report_type == "expense":
            return self._expense_report(params)
        else:
            return {"error": "Unknown report type"}

    def _sales_report(self, params):
        date_from = params.get("date_from",
                               (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d"))
        date_to = params.get("date_to", datetime.now().strftime("%Y-%m-%d"))
        invoices = self.billing.get_invoices(date_from=date_from, date_to=date_to)
        top_products = self.billing.get_top_products(10, 30)
        summary = {
            "total_invoices": len(invoices),
            "total_revenue": sum(float(i.get("total_amount") or 0) for i in invoices),
            "total_tax": sum(float(i.get("tax_amount") or 0) for i in invoices),
            "date_from": date_from,
            "date_to": date_to,
        }
        return {"summary": summary, "invoices": invoices, "top_products": top_products}

    def _inventory_report(self, params):
        from app.controllers.product_controller import ProductController
        pc = ProductController()
        return {
            "all_products": pc.get_all_products(),
            "low_stock": pc.get_low_stock_products(),
            "out_of_stock": pc.get_out_of_stock_products(),
            "value": pc.get_inventory_value(),
        }

    def _customer_report(self, params):
        from app.controllers.customer_controller import CustomerController
        cc = CustomerController()
        return {
            "all_customers": cc.get_all_customers(),
            "top_customers": cc.get_top_customers(20),
        }

    def _expense_report(self, params):
        from app.controllers.expense_employee_controller import ExpenseController
        ec = ExpenseController()
        return {
            "expenses": ec.get_expenses(),
            "summary": ec.get_expense_summary("month"),
        }


class AIController:
    """AI-powered predictions and business assistant."""

    def __init__(self):
        self.db = DatabaseManager()

    def predict_sales(self, days_ahead=7):
        """
        Predict future sales using linear regression on historical data.
        Returns predictions for the next N days.
        """
        try:
            import numpy as np
            from sklearn.linear_model import LinearRegression

            # Get last 90 days of sales
            history = self.db.fetchall(
                """SELECT DATE(invoice_date) as date,
                   SUM(total_amount) as revenue
                   FROM invoices
                   WHERE DATE(invoice_date) >= DATE('now', '-90 days')
                   GROUP BY DATE(invoice_date)
                   ORDER BY date"""
            )

            if len(history) < 7:
                return self._fallback_prediction(days_ahead)

            revenues = np.array([float(r.get("revenue") or 0) for r in history])
            X = np.arange(len(revenues)).reshape(-1, 1)

            model = LinearRegression()
            model.fit(X, revenues)

            future_X = np.arange(len(revenues), len(revenues) + days_ahead).reshape(-1, 1)
            predictions = model.predict(future_X)

            result = []
            today = datetime.now()
            for i, pred in enumerate(predictions):
                future_date = (today + timedelta(days=i + 1)).strftime("%Y-%m-%d")
                result.append({
                    "date": future_date,
                    "predicted_sales": max(0, round(float(pred), 2)),
                    "confidence": min(0.95, 0.6 + (len(history) / 90) * 0.35)
                })

            # Cache predictions
            for r in result:
                self.db.execute(
                    """INSERT OR REPLACE INTO ai_predictions
                       (prediction_type, target_date, predicted_value, confidence)
                       VALUES (?,?,?,?)""",
                    ("sales", r["date"], r["predicted_sales"], r["confidence"])
                )

            return {"success": True, "predictions": result}

        except ImportError:
            logger.warning("scikit-learn not available, using fallback")
            return self._fallback_prediction(days_ahead)
        except Exception as e:
            logger.error(f"AI prediction error: {e}")
            return {"success": False, "error": str(e)}

    def predict_restock(self, product_id: int = None):
        """
        Predict restock requirements based on sales velocity.
        """
        try:
            import numpy as np
            products_to_analyze = []
            if product_id:
                from app.controllers.product_controller import ProductController
                pc = ProductController()
                p = pc.get_product(product_id)
                if p:
                    products_to_analyze = [p]
            else:
                products_to_analyze = self.db.fetchall(
                    """SELECT p.* FROM products p
                       WHERE p.is_active=1 AND p.quantity <= p.min_stock * 2
                       ORDER BY p.quantity ASC LIMIT 20"""
                )

            recommendations = []
            for product in products_to_analyze:
                pid = product["id"]
                # Calculate 30-day sales velocity
                sales_data = self.db.fetchall(
                    """SELECT SUM(ii.quantity) as qty_sold
                       FROM invoice_items ii
                       JOIN invoices i ON ii.invoice_id=i.id
                       WHERE ii.product_id=? AND
                       DATE(i.invoice_date) >= DATE('now', '-30 days')""",
                    (pid,)
                )
                qty_sold_30d = float(sales_data[0].get("qty_sold") or 0) if sales_data else 0
                daily_velocity = qty_sold_30d / 30
                days_of_stock = (
                    float(product.get("quantity", 0)) / daily_velocity
                    if daily_velocity > 0 else 999
                )
                reorder_qty = max(
                    int(daily_velocity * 30),
                    int(product.get("min_stock", 10))
                )

                recommendations.append({
                    "product_id": pid,
                    "product_name": product["name"],
                    "current_stock": product.get("quantity", 0),
                    "daily_velocity": round(daily_velocity, 2),
                    "days_of_stock_remaining": round(days_of_stock, 1),
                    "recommended_reorder_qty": reorder_qty,
                    "urgency": "critical" if days_of_stock < 3 else (
                        "high" if days_of_stock < 7 else "normal"
                    )
                })

            return {"success": True, "recommendations": recommendations}

        except Exception as e:
            logger.error(f"Restock prediction error: {e}")
            return {"success": False, "error": str(e)}

    def business_assistant(self, query: str):
        """
        Rule-based business assistant that answers inventory/sales queries.
        """
        query_lower = query.lower()

        # Sales queries
        if any(w in query_lower for w in ["today sales", "today's sales", "sales today"]):
            from app.controllers.billing_controller import BillingController
            bc = BillingController()
            data = bc.get_sales_summary("today")
            rev = float(data.get("total_revenue") or 0)
            orders = int(data.get("total_orders") or 0)
            return f"📊 Today's Sales:\n• Revenue: ₹{rev:,.2f}\n• Orders: {orders}"

        elif "month" in query_lower and "sales" in query_lower:
            from app.controllers.billing_controller import BillingController
            bc = BillingController()
            data = bc.get_sales_summary("month")
            rev = float(data.get("total_revenue") or 0)
            return f"📈 This Month's Sales: ₹{rev:,.2f}"

        elif any(w in query_lower for w in ["low stock", "out of stock", "stock alert"]):
            from app.controllers.product_controller import ProductController
            pc = ProductController()
            low = pc.get_low_stock_products()
            out = pc.get_out_of_stock_products()
            return (f"⚠️ Stock Alerts:\n• Low Stock: {len(low)} products\n"
                    f"• Out of Stock: {len(out)} products")

        elif any(w in query_lower for w in ["top product", "best selling"]):
            from app.controllers.billing_controller import BillingController
            bc = BillingController()
            top = bc.get_top_products(5)
            if not top:
                return "No sales data available yet."
            result = "🏆 Top 5 Products:\n"
            for i, p in enumerate(top, 1):
                result += f"{i}. {p['product_name']} - ₹{float(p['total_revenue'] or 0):,.2f}\n"
            return result

        elif "customer" in query_lower:
            total = self.db.fetchone(
                "SELECT COUNT(*) as cnt FROM customers WHERE is_active=1")
            count = int(total.get("cnt") or 0) if total else 0
            return f"👥 Total Customers: {count}"

        elif "expense" in query_lower:
            from app.controllers.expense_employee_controller import ExpenseController
            ec = ExpenseController()
            total = ec.get_total_expenses("month")
            return f"💸 Monthly Expenses: ₹{total:,.2f}"

        elif "profit" in query_lower:
            from app.controllers.analytics_controller import AnalyticsController
            ac = AnalyticsController()
            kpis = ac.get_dashboard_kpis()
            return f"💰 Net Profit (This Month): ₹{kpis['net_profit']:,.2f}"

        elif "predict" in query_lower or "forecast" in query_lower:
            preds = self.predict_sales(7)
            if preds.get("success") and preds.get("predictions"):
                result = "🔮 7-Day Sales Forecast:\n"
                for p in preds["predictions"]:
                    result += f"• {p['date']}: ₹{p['predicted_sales']:,.2f}\n"
                return result
            return "Insufficient data for predictions."

        else:
            return (
                "🤖 SmartPOS AI Assistant\n\n"
                "I can help you with:\n"
                "• Today's sales / Monthly sales\n"
                "• Low stock / Out of stock alerts\n"
                "• Top selling products\n"
                "• Customer count\n"
                "• Monthly expenses\n"
                "• Net profit\n"
                "• Sales forecast\n\n"
                "Try: 'Show today sales' or 'Low stock alert'"
            )

    def _fallback_prediction(self, days_ahead):
        """Simple moving average fallback."""
        history = self.db.fetchall(
            """SELECT SUM(total_amount) as revenue
               FROM invoices
               WHERE DATE(invoice_date) >= DATE('now', '-7 days')
               GROUP BY DATE(invoice_date)"""
        )
        avg = 0
        if history:
            vals = [float(r.get("revenue") or 0) for r in history]
            avg = sum(vals) / len(vals) if vals else 0

        today = datetime.now()
        result = []
        for i in range(days_ahead):
            result.append({
                "date": (today + timedelta(days=i + 1)).strftime("%Y-%m-%d"),
                "predicted_sales": round(avg * (0.95 + (i * 0.01)), 2),
                "confidence": 0.5
            })
        return {"success": True, "predictions": result}

