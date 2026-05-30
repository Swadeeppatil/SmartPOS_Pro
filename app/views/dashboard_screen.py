"""
SmartPOS Pro - Dashboard Screen (KivyMD)
"""
from kivymd.uix.screen import MDScreen
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.gridlayout import MDGridLayout
from kivymd.uix.card import MDCard
from kivymd.uix.label import MDLabel
from kivymd.uix.button import MDIconButton, MDRaisedButton
from kivymd.uix.scrollview import MDScrollView
from kivy.metrics import dp
from kivy.clock import Clock
from kivy.properties import StringProperty, NumericProperty
from app.controllers.analytics_controller import AnalyticsController
from app.utils.helpers import format_currency


class KPICard(MDCard):
    """Reusable KPI widget card."""
    title = StringProperty("")
    value = StringProperty("0")
    icon = StringProperty("chart-bar")
    trend = StringProperty("")
    card_color = StringProperty("#2563EB")


class DashboardScreen(MDScreen):
    """Main dashboard with live KPIs and charts."""

    def on_enter(self):
        Clock.schedule_once(self._load_data, 0.1)

    def _load_data(self, dt=None):
        try:
            self.analytics = AnalyticsController()
            kpis = self.analytics.get_dashboard_kpis()
            self._update_kpi_cards(kpis)
            self._load_chart()
            self._load_top_products()
            self._load_notifications()
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Dashboard load error: {e}")

    def _update_kpi_cards(self, kpis):
        cards = [
            ("Today's Sales", format_currency(kpis.get("today_sales", 0)),
             "cash-register", "#10B981"),
            ("Monthly Sales", format_currency(kpis.get("month_sales", 0)),
             "chart-line", "#2563EB"),
            ("Net Profit", format_currency(kpis.get("net_profit", 0)),
             "trending-up", "#06B6D4"),
            ("Total Products", str(kpis.get("total_products", 0)),
             "package-variant", "#8B5CF6"),
            ("Customers", str(kpis.get("total_customers", 0)),
             "account-group", "#F59E0B"),
            ("Today Orders", str(kpis.get("today_orders", 0)),
             "receipt", "#EF4444"),
            ("Low Stock", str(kpis.get("low_stock_count", 0)),
             "alert-circle", "#F97316"),
            ("Pending Due", format_currency(kpis.get("pending_payments", 0)),
             "clock-alert", "#DC2626"),
        ]
        grid = self.ids.kpi_grid
        grid.clear_widgets()
        for title, value, icon, color in cards:
            card = KPICard()
            card.title = title
            card.value = value
            card.icon = icon
            card.card_color = color
            card.md_bg_color = self._hex_to_color(color + "22")
            grid.add_widget(card)

    def _load_chart(self):
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            import io
            from kivy.core.image import Image as CoreImage
            from kivy.uix.image import Image as KivyImage

            data = self.analytics.get_sales_chart_data("30days")
            if not data["dates"]:
                return

            fig, ax = plt.subplots(figsize=(8, 2.5))
            fig.patch.set_facecolor("#1E293B")
            ax.set_facecolor("#1E293B")

            ax.fill_between(range(len(data["dates"])), data["revenues"],
                            alpha=0.3, color="#2563EB")
            ax.plot(range(len(data["dates"])), data["revenues"],
                    color="#2563EB", linewidth=2)

            ax.set_xticks(range(0, len(data["dates"]), max(1, len(data["dates"]) // 7)))
            ax.set_xticklabels(
                [data["dates"][i][-5:] for i in
                 range(0, len(data["dates"]), max(1, len(data["dates"]) // 7))],
                color="#94A3B8", fontsize=7, rotation=30
            )
            ax.tick_params(colors="#94A3B8")
            ax.spines[:].set_color("#334155")
            ax.yaxis.label.set_color("#94A3B8")
            plt.tight_layout(pad=0.5)

            buf = io.BytesIO()
            plt.savefig(buf, format="png", dpi=100, bbox_inches="tight")
            buf.seek(0)
            plt.close(fig)

            core_img = CoreImage(buf, ext="png")
            chart_widget = self.ids.chart_container
            chart_widget.clear_widgets()
            img = KivyImage(texture=core_img.texture, size_hint_y=None, height=dp(160))
            chart_widget.add_widget(img)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Chart error: {e}")

    def _load_top_products(self):
        try:
            top = self.analytics.billing.get_top_products(5)
            container = self.ids.top_products_list
            container.clear_widgets()
            for i, product in enumerate(top, 1):
                row = MDBoxLayout(
                    orientation="horizontal",
                    size_hint_y=None, height=dp(36),
                    spacing=dp(8), padding=[dp(4), 0]
                )
                row.add_widget(MDLabel(
                    text=f"{i}.", size_hint_x=0.08,
                    theme_text_color="Secondary", font_style="Caption"
                ))
                row.add_widget(MDLabel(
                    text=product.get("product_name", ""),
                    size_hint_x=0.55, theme_text_color="Primary",
                    font_style="Body2"
                ))
                row.add_widget(MDLabel(
                    text=format_currency(product.get("total_revenue", 0)),
                    size_hint_x=0.37, halign="right",
                    theme_text_color="Custom",
                    text_color=self._hex_to_color("#10B981"),
                    font_style="Body2"
                ))
                container.add_widget(row)
        except Exception as e:
            pass

    def _load_notifications(self):
        try:
            from app.utils.helpers import NotificationManager
            nm = NotificationManager()
            nm.check_and_send_stock_alerts()
            count = nm.get_unread_count()
            if count > 0:
                self.ids.notif_badge.text = str(count)
        except Exception:
            pass

    def refresh(self):
        self._load_data()

    def navigate_to(self, screen_name):
        self.manager.current = screen_name

    @staticmethod
    def _hex_to_color(hex_str):
        h = hex_str.lstrip("#")
        if len(h) == 8:
            r, g, b, a = [int(h[i:i+2], 16)/255 for i in (0, 2, 4, 6)]
        else:
            r, g, b = [int(h[i:i+2], 16)/255 for i in (0, 2, 4)]
            a = 1
        return (r, g, b, a)


