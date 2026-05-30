"""SmartPOS Pro - Analytics, Reports, AI Assistant, Settings screens."""
from kivymd.uix.screen import MDScreen
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.label import MDLabel
from kivymd.uix.button import MDRaisedButton, MDFlatButton
from kivymd.uix.textfield import MDTextField
from kivymd.uix.scrollview import MDScrollView
from app.utils.compat import show_snackbar
from kivy.metrics import dp
from kivy.clock import Clock


class AnalyticsScreen(MDScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        from app.controllers.analytics_controller import AnalyticsController
        self.ctrl = AnalyticsController()

    def on_enter(self):
        Clock.schedule_once(self._load, 0.15)

    def _load(self, dt=None):
        self._draw_revenue_chart()
        self._draw_category_chart()
        self._load_top_products()

    def _draw_revenue_chart(self):
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt, io
            from kivy.core.image import Image as CoreImage
            from kivy.uix.image import Image as KivyImage
            data = self.ctrl.get_sales_chart_data("30days")
            if not data["dates"]:
                return
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(8, 4))
            fig.patch.set_facecolor("#1E293B")
            for ax in (ax1, ax2):
                ax.set_facecolor("#1E293B")
                ax.tick_params(colors="#94A3B8", labelsize=7)
                ax.spines[:].set_color("#334155")
            ax1.plot(data["revenues"], color="#2563EB", linewidth=2)
            ax1.fill_between(range(len(data["revenues"])), data["revenues"],
                             alpha=0.2, color="#2563EB")
            ax1.set_title("Revenue (30 days)", color="#F1F5F9", fontsize=9)
            ax2.bar(range(len(data["orders"])), data["orders"],
                    color="#06B6D4", alpha=0.8)
            ax2.set_title("Orders (30 days)", color="#F1F5F9", fontsize=9)
            plt.tight_layout(pad=0.5)
            buf = io.BytesIO()
            plt.savefig(buf, format="png", dpi=100, bbox_inches="tight")
            buf.seek(0); plt.close(fig)
            core_img = CoreImage(buf, ext="png")
            container = self.ids.chart_box
            container.clear_widgets()
            container.add_widget(KivyImage(texture=core_img.texture,
                                           size_hint_y=None, height=dp(220)))
        except Exception as e:
            import logging; logging.getLogger(__name__).warning(f"Chart: {e}")

    def _draw_category_chart(self):
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt, io
            from kivy.core.image import Image as CoreImage
            from kivy.uix.image import Image as KivyImage
            data = self.ctrl.get_category_sales()
            if not data:
                return
            labels = [d.get("category") or "Other" for d in data[:6]]
            values = [float(d.get("revenue") or 0) for d in data[:6]]
            colors = ["#2563EB","#06B6D4","#10B981","#F59E0B","#EF4444","#8B5CF6"]
            fig, ax = plt.subplots(figsize=(5, 3))
            fig.patch.set_facecolor("#1E293B")
            ax.set_facecolor("#1E293B")
            ax.pie(values, labels=labels, colors=colors,
                   textprops={"color": "#F1F5F9", "fontsize": 7},
                   autopct="%1.0f%%")
            ax.set_title("Sales by Category", color="#F1F5F9", fontsize=9)
            buf = io.BytesIO()
            plt.savefig(buf, format="png", dpi=100, bbox_inches="tight")
            buf.seek(0); plt.close(fig)
            core_img = CoreImage(buf, ext="png")
            container = self.ids.pie_box
            container.clear_widgets()
            container.add_widget(KivyImage(texture=core_img.texture,
                                           size_hint_y=None, height=dp(180)))
        except Exception as e:
            pass

    def _load_top_products(self):
        from app.utils.helpers import format_currency
        top = self.ctrl.billing.get_top_products(10)
        container = self.ids.top_list
        container.clear_widgets()
        for i, p in enumerate(top, 1):
            row = MDBoxLayout(orientation="horizontal", size_hint_y=None,
                              height=dp(40), spacing=dp(8), padding=[dp(4), 0])
            row.add_widget(MDLabel(text=f"{i}.", size_hint_x=0.08,
                                   theme_text_color="Secondary"))
            row.add_widget(MDLabel(text=p.get("product_name",""), size_hint_x=0.55))
            row.add_widget(MDLabel(text=str(int(p.get("total_qty") or 0)),
                                   size_hint_x=0.17, theme_text_color="Secondary"))
            row.add_widget(MDLabel(
                text=format_currency(p.get("total_revenue",0)),
                size_hint_x=0.2, halign="right",
                theme_text_color="Custom",
                text_color=(0.063, 0.725, 0.506, 1)))
            container.add_widget(row)

    def generate_report(self, report_type="sales"):
        data = self.ctrl.generate_report(report_type)
        self._export_pdf(data, report_type)

    def _export_pdf(self, data, report_type):
        import os
        os.makedirs("exports", exist_ok=True)
        from datetime import datetime
        filename = f"exports/{report_type}_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.lib import colors
            doc = SimpleDocTemplate(filename, pagesize=A4)
            styles = getSampleStyleSheet()
            story = [
                Paragraph(f"SmartPOS Pro - {report_type.title()} Report", styles["Title"]),
                Spacer(1, 12),
                Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", styles["Normal"]),
                Spacer(1, 12),
            ]
            summary = data.get("summary", {})
            if summary:
                for k, v in summary.items():
                    story.append(Paragraph(f"<b>{k.replace('_',' ').title()}:</b> {v}", styles["Normal"]))
                story.append(Spacer(1, 12))
            doc.build(story)
            show_snackbar(f"Report saved: {filename}")
            import platform
            try:
                if platform.system() == 'Darwin':
                    os.system(f'open "{filename}"')
                elif platform.system() == 'Windows':
                    os.startfile(os.path.abspath(filename))
                else:
                    os.system(f'xdg-open "{filename}"')
            except Exception:
                pass
        except Exception as e:
            show_snackbar(f"PDF error: {e}")


class ReportsScreen(MDScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        from app.controllers.billing_controller import BillingController
        self.billing = BillingController()

    def on_enter(self):
        Clock.schedule_once(self._load_recent, 0.15)

    def _load_recent(self, dt=None):
        from app.utils.helpers import format_currency
        invoices = self.billing.get_invoices(limit=30)
        container = self.ids.invoices_list
        container.clear_widgets()
        for inv in invoices:
            row = MDBoxLayout(orientation="horizontal", size_hint_y=None,
                              height=dp(52), spacing=dp(8), padding=[dp(8), dp(4)])
            row.add_widget(MDLabel(text=inv.get("invoice_number",""), size_hint_x=0.25))
            row.add_widget(MDLabel(
                text=inv.get("customer_name","Walk-in"), size_hint_x=0.3,
                theme_text_color="Secondary"))
            row.add_widget(MDLabel(
                text=format_currency(inv.get("total_amount",0)),
                size_hint_x=0.2,
                theme_text_color="Custom",
                text_color=(0.063, 0.725, 0.506, 1)))
            status = inv.get("payment_status","paid")
            status_color = (0.063, 0.725, 0.506, 1) if status=="paid" else (0.937, 0.267, 0.267, 1)
            row.add_widget(MDLabel(
                text=status.upper(), size_hint_x=0.15,
                theme_text_color="Custom", text_color=status_color))
            row.add_widget(MDLabel(
                text=str(inv.get("invoice_date",""))[:10],
                size_hint_x=0.1, theme_text_color="Secondary"))
            container.add_widget(row)

    def filter_by_date(self, date_from, date_to):
        from app.utils.helpers import format_currency
        invoices = self.billing.get_invoices(date_from=date_from, date_to=date_to)
        show_snackbar(f"Showing {len(invoices)} invoices")

    def export_csv(self):
        import csv, os
        os.makedirs("exports", exist_ok=True)
        invoices = self.billing.get_invoices(limit=1000)
        path = "exports/sales_report.csv"
        with open(path, "w", newline="", encoding="utf-8") as f:
            if invoices:
                w = csv.DictWriter(f, fieldnames=invoices[0].keys())
                w.writeheader()
                w.writerows(invoices)
        show_snackbar(f"Exported to {path}")


class AIAssistantScreen(MDScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        from app.controllers.analytics_controller import AIController
        self.ai = AIController()
        self._chat_history = []

    def on_enter(self):
        self._append_message("SmartPOS AI", self.ai.business_assistant("help"), is_bot=True)

    def send_message(self):
        query = self.ids.input_field.text.strip()
        if not query:
            return
        self.ids.input_field.text = ""
        self._append_message("You", query)
        Clock.schedule_once(lambda dt: self._get_response(query), 0.2)

    def _get_response(self, query):
        response = self.ai.business_assistant(query)
        self._append_message("SmartPOS AI", response, is_bot=True)

    def _append_message(self, sender, text, is_bot=False):
        container = self.ids.chat_container
        msg = MDBoxLayout(orientation="vertical", size_hint_y=None,
                          padding=[dp(8), dp(6)], spacing=dp(2))
        msg.bind(minimum_height=msg.setter("height"))
        sender_lbl = MDLabel(
            text=sender, font_style="Caption",
            size_hint_y=None, height=dp(18),
            theme_text_color="Custom",
            text_color=(0.039, 0.714, 0.600, 1) if is_bot else (0.388, 0.631, 0.929, 1)
        )
        text_lbl = MDLabel(text=text, size_hint_y=None, adaptive_height=True)
        msg.add_widget(sender_lbl)
        msg.add_widget(text_lbl)
        container.add_widget(msg)
        self.ids.chat_scroll.scroll_y = 0

    def predict_sales(self):
        result = self.ai.predict_sales(7)
        if result.get("success"):
            preds = result["predictions"]
            text = "📈 7-Day Forecast:\n" + "\n".join(
                f"• {p['date']}: ₹{p['predicted_sales']:,.0f} (conf {p['confidence']:.0%})"
                for p in preds)
        else:
            text = f"Prediction failed: {result.get('error','')}"
        self._append_message("SmartPOS AI", text, is_bot=True)

    def predict_restock(self):
        result = self.ai.predict_restock()
        if result.get("success"):
            recs = result["recommendations"]
            if not recs:
                text = "✅ All products have adequate stock."
            else:
                text = "📦 Restock Recommendations:\n" + "\n".join(
                    f"• {r['product_name']}: Order {r['recommended_reorder_qty']} units "
                    f"({r['days_of_stock_remaining']:.0f} days left)" for r in recs[:10])
        else:
            text = f"Error: {result.get('error','')}"
        self._append_message("SmartPOS AI", text, is_bot=True)


class SettingsScreen(MDScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        from app.utils.helpers import BackupManager
        self.backup_mgr = BackupManager()

    def on_enter(self):
        self._load_settings()

    def _load_settings(self):
        from app.models.database import DatabaseManager
        db = DatabaseManager()
        settings = db.fetchall("SELECT key, value FROM settings")
        for s in settings:
            widget_id = f"setting_{s['key']}"
            if hasattr(self.ids, widget_id):
                getattr(self.ids, widget_id).text = s["value"] or ""

    def save_settings(self):
        from app.models.database import DatabaseManager
        db = DatabaseManager()
        from datetime import datetime
        for key in ["shop_name", "shop_phone", "shop_address", "shop_gst",
                    "currency_symbol", "tax_rate"]:
            widget_id = f"setting_{key}"
            if hasattr(self.ids, widget_id):
                val = getattr(self.ids, widget_id).text.strip()
                existing = db.fetchone("SELECT id FROM settings WHERE key=?", (key,))
                if existing:
                    db.execute("UPDATE settings SET value=?, updated_at=? WHERE key=?",
                               (val, datetime.now().isoformat(), key))
                else:
                    db.execute("INSERT INTO settings (key, value) VALUES (?,?)", (key, val))
        show_snackbar("Settings saved!")

    def create_backup(self):
        r = self.backup_mgr.create_backup("manual")
        msg = f"Backup: {r.get('filename','')}" if r["success"] else r["message"]
        show_snackbar(msg)

    def export_json(self):
        import os
        os.makedirs("exports", exist_ok=True)
        r = self.backup_mgr.export_data_json("exports/smartpos_data.json")
        show_snackbar("Data exported to JSON!" if r["success"] else r["message"])

    def change_theme(self, style):
        self.app.theme_cls.theme_style = style

    def manage_users(self):
        self.manager.current = "users"


