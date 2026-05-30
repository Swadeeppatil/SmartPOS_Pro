"""
SmartPOS Pro - Main Entry Point (KivyMD 1.2.0)
Single MDNavigationLayout root; login/splash guard via MDScreenManager.
"""
import os, sys, logging
from kivy.lang import Builder
from kivy.core.window import Window
from kivy.clock import Clock
from kivy.metrics import dp
from kivymd.app import MDApp
from kivymd.uix.navigationdrawer import MDNavigationDrawer, MDNavigationLayout
from kivymd.uix.screenmanager import MDScreenManager
from kivy.uix.screenmanager import SlideTransition

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.utils.helpers import setup_logging
from app.utils.theme import THEME_PRIMARY, THEME_ACCENT, THEME_STYLE

from app.views.login_screen      import SplashScreen, LoginScreen
from app.views.dashboard_screen  import DashboardScreen, KPICard
from app.views.products_screen   import ProductsScreen, ProductCard, ProductFormContent
from app.views.pos_screen        import POSScreen, PaymentContent
from app.views.management_screens import (
    CustomersScreen, SuppliersScreen, InventoryScreen,
    EmployeesScreen, ExpensesScreen, GenericForm,
)
from app.views.analytics_screens import (
    AnalyticsScreen, ReportsScreen, AIAssistantScreen, SettingsScreen,
)
from app.views.nav_drawer import NavDrawerContent


class SmartPOSApp(MDApp):

    def __init__(self, **kw):
        super().__init__(**kw)
        self.title        = "SmartPOS Pro"
        self.auth         = None
        self.current_user = None
        self._drawer      = None
        self._sm          = None

    # ------------------------------------------------------------------ build
    def build(self):
        setup_logging()
        self.theme_cls.primary_palette = THEME_PRIMARY
        self.theme_cls.accent_palette  = THEME_ACCENT
        self.theme_cls.theme_style     = THEME_STYLE

        if sys.platform != "android":
            Window.size = (1024, 680)

        # Load KV
        kv_path = os.path.join(os.path.dirname(__file__),
                               "app", "views", "smartpos.kv")
        Builder.load_file(kv_path)

        # Single ScreenManager for EVERY screen (auth + main)
        sm = MDScreenManager(transition=SlideTransition())
        self._sm = sm

        for s in [
            SplashScreen    (name="splash"),
            LoginScreen     (name="login"),
            DashboardScreen (name="dashboard"),
            ProductsScreen  (name="products"),
            POSScreen       (name="pos"),
            InventoryScreen (name="inventory"),
            CustomersScreen (name="customers"),
            SuppliersScreen (name="suppliers"),
            EmployeesScreen (name="employees"),
            ExpensesScreen  (name="expenses"),
            AnalyticsScreen (name="analytics"),
            ReportsScreen   (name="reports"),
            AIAssistantScreen(name="ai_assistant"),
            SettingsScreen  (name="settings"),
        ]:
            sm.add_widget(s)

        sm.current = "splash"

        # Drawer
        drawer = MDNavigationDrawer(width=dp(260))
        nav_content = NavDrawerContent()
        nav_content.screen_manager = sm
        nav_content.nav_drawer     = drawer
        drawer.add_widget(nav_content)
        self._drawer = drawer

        # Root layout
        root = MDNavigationLayout()
        root.add_widget(sm)
        root.add_widget(drawer)

        Clock.schedule_interval(self._auto_backup, 86400)
        Clock.schedule_once(self._check_alerts, 8)
        return root

    # ---------------------------------------------------------------- helpers
    def on_login_success(self, auth, user):
        self.auth         = auth
        self.current_user = user
        if self._sm:
            self._sm.current_user = user
            self._sm.auth         = auth
            self._sm.current      = "dashboard"

    def open_drawer(self):
        if self._drawer:
            self._drawer.set_state("open")

    def navigate(self, screen_name):
        if self._sm:
            try:
                self._sm.current = screen_name
            except Exception:
                pass

    def logout(self):
        try:
            from app.utils.session import SessionManager
            SessionManager().clear()
        except Exception:
            pass
        if self.auth:
            try: self.auth.logout()
            except Exception: pass
        self.auth         = None
        self.current_user = None
        if self._sm:
            self._sm.current_user = None
            self._sm.auth         = None
            self._sm.current      = "login"

    def _auto_backup(self, dt):
        try:
            from app.utils.helpers import BackupManager
            BackupManager().create_backup("auto")
        except Exception as e:
            logging.getLogger(__name__).error(f"Backup: {e}")

    def _check_alerts(self, dt):
        try:
            from app.utils.helpers import NotificationManager
            NotificationManager().check_and_send_stock_alerts()
        except Exception as e:
            logging.getLogger(__name__).error(f"Alerts: {e}")

    def on_pause(self):  return True
    def on_resume(self): pass


if __name__ == "__main__":
    SmartPOSApp().run()
