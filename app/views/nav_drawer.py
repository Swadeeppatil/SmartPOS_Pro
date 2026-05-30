"""
SmartPOS Pro - Navigation Drawer Screen
Wraps all content screens with side drawer navigation.
"""
from kivymd.uix.screen import MDScreen
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.label import MDLabel
from kivymd.uix.button import MDFlatButton, MDRaisedButton, MDIconButton
from kivymd.uix.list import MDList, OneLineIconListItem, IconLeftWidget
from kivy.metrics import dp
from kivy.clock import Clock
from kivy.properties import StringProperty, ObjectProperty


NAV_ITEMS = [
    ("view-dashboard",   "Dashboard",    "dashboard"),
    ("package-variant",  "Products",     "products"),
    ("point-of-sale",    "POS Billing",  "pos"),
    ("warehouse",        "Inventory",    "inventory"),
    ("account-group",    "Customers",    "customers"),
    ("truck-delivery",   "Suppliers",    "suppliers"),
    ("account-hard-hat", "Employees",    "employees"),
    ("cash",             "Expenses",     "expenses"),
    ("chart-line",       "Analytics",    "analytics"),
    ("file-chart",       "Reports",      "reports"),
    ("robot",            "AI Assistant", "ai_assistant"),
    ("cog",              "Settings",     "settings"),
]


class NavDrawerContent(MDBoxLayout):
    """Side navigation drawer content."""

    screen_manager = ObjectProperty(None)
    nav_drawer     = ObjectProperty(None)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation  = "vertical"
        self.spacing      = dp(4)
        self.padding      = [0, dp(8), 0, dp(8)]
        self.md_bg_color  = (0.059, 0.090, 0.161, 1)
        Clock.schedule_once(self._build, 0)

    def _build(self, *args):
        # Header
        header = MDBoxLayout(
            orientation="vertical",
            size_hint_y=None,
            height=dp(90),
            padding=[dp(16), dp(12)],
            md_bg_color=(0.149, 0.388, 0.922, 1),
        )
        header.add_widget(MDLabel(
            text="SmartPOS Pro",
            font_style="H6",
            bold=True,
            theme_text_color="Custom",
            text_color=(1, 1, 1, 1),
            size_hint_y=None,
            height=dp(32),
        ))
        header.add_widget(MDLabel(
            text="Inventory & Billing",
            font_style="Caption",
            theme_text_color="Custom",
            text_color=(0.8, 0.9, 1, 1),
            size_hint_y=None,
            height=dp(20),
        ))
        self.add_widget(header)

        # Nav list
        from kivymd.uix.scrollview import MDScrollView
        scroll = MDScrollView()
        nav_list = MDList()

        for icon, label, target in NAV_ITEMS:
            item = OneLineIconListItem(
                text=label,
                on_release=lambda x, t=target: self._navigate(t),
            )
            item.add_widget(IconLeftWidget(icon=icon))
            nav_list.add_widget(item)

        scroll.add_widget(nav_list)
        self.add_widget(scroll)

        # Footer — logout
        logout_btn = MDFlatButton(
            text="  Logout",
            icon="logout",
            size_hint_y=None,
            height=dp(48),
            theme_text_color="Custom",
            text_color=(0.937, 0.267, 0.267, 1),
            on_release=self._logout,
        )
        self.add_widget(logout_btn)

    def _navigate(self, target):
        if self.nav_drawer:
            self.nav_drawer.set_state("close")
        if self.screen_manager:
            try:
                self.screen_manager.current = target
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Nav error: {e}")

    def _logout(self, *args):
        if self.nav_drawer:
            self.nav_drawer.set_state("close")
        try:
            from kivy.app import App
            App.get_running_app().logout()
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Logout error: {e}")
