"""
SmartPOS Pro - KivyMD Theme & Style Configuration
"""

# Application theme constants
APP_NAME = "SmartPOS Pro"
APP_VERSION = "1.0.0"

# KivyMD Material Theme
THEME_PRIMARY = "Blue"
THEME_ACCENT = "Cyan"
THEME_STYLE = "Dark"   # "Dark" or "Light"

# Brand Colors (hex)
COLOR_PRIMARY = "#2563EB"
COLOR_PRIMARY_DARK = "#1D4ED8"
COLOR_ACCENT = "#06B6D4"
COLOR_SUCCESS = "#10B981"
COLOR_WARNING = "#F59E0B"
COLOR_DANGER = "#EF4444"
COLOR_INFO = "#3B82F6"
COLOR_BG_DARK = "#0F172A"
COLOR_SURFACE_DARK = "#1E293B"
COLOR_CARD_DARK = "#334155"
COLOR_TEXT = "#F1F5F9"
COLOR_TEXT_SECONDARY = "#94A3B8"

# KV Color tuples for Kivy (R, G, B, A)
def hex_to_kivy(hex_color: str):
    """Convert hex to Kivy RGBA tuple (0-1 range)."""
    h = hex_color.lstrip("#")
    r, g, b = [int(h[i:i+2], 16) / 255 for i in (0, 2, 4)]
    return (r, g, b, 1)


KIVY_PRIMARY = hex_to_kivy(COLOR_PRIMARY)
KIVY_ACCENT = hex_to_kivy(COLOR_ACCENT)
KIVY_SUCCESS = hex_to_kivy(COLOR_SUCCESS)
KIVY_WARNING = hex_to_kivy(COLOR_WARNING)
KIVY_DANGER = hex_to_kivy(COLOR_DANGER)
KIVY_BG = hex_to_kivy(COLOR_BG_DARK)
KIVY_SURFACE = hex_to_kivy(COLOR_SURFACE_DARK)
KIVY_CARD = hex_to_kivy(COLOR_CARD_DARK)

# Navigation items
NAV_ITEMS = [
    {"icon": "view-dashboard", "text": "Dashboard", "screen": "dashboard"},
    {"icon": "package-variant", "text": "Products", "screen": "products"},
    {"icon": "point-of-sale", "text": "POS", "screen": "pos"},
    {"icon": "warehouse", "text": "Inventory", "screen": "inventory"},
    {"icon": "account-group", "text": "Customers", "screen": "customers"},
    {"icon": "truck-delivery", "text": "Suppliers", "screen": "suppliers"},
    {"icon": "account-hard-hat", "text": "Employees", "screen": "employees"},
    {"icon": "chart-line", "text": "Analytics", "screen": "analytics"},
    {"icon": "file-chart", "text": "Reports", "screen": "reports"},
    {"icon": "cash", "text": "Expenses", "screen": "expenses"},
    {"icon": "cog", "text": "Settings", "screen": "settings"},
]

# Units
UNITS = ["pcs", "kg", "g", "ltr", "ml", "box", "dozen", "pair", "set",
         "meter", "yard", "sqft", "packet", "bottle", "can", "bag"]

# GST rates
GST_RATES = [0, 5, 12, 18, 28]

# Payment methods
PAYMENT_METHODS = ["Cash", "Card", "UPI", "Wallet", "Net Banking", "Split"]

# Membership types
MEMBERSHIP_TYPES = ["regular", "silver", "gold", "platinum"]
