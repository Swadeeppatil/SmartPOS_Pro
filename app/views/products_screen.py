"""
SmartPOS Pro - Products Screen (KivyMD)
Full CRUD UI with search, filter, barcode generation.
"""
from kivymd.uix.screen import MDScreen
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.gridlayout import MDGridLayout
from kivymd.uix.card import MDCard
from kivymd.uix.label import MDLabel
from kivymd.uix.button import MDRaisedButton, MDFlatButton, MDIconButton
from kivymd.uix.textfield import MDTextField
from kivymd.uix.scrollview import MDScrollView
from kivymd.uix.dialog import MDDialog
from app.utils.compat import show_snackbar
from kivymd.uix.menu import MDDropdownMenu
from kivymd.uix.selectioncontrol import MDCheckbox
from kivy.metrics import dp
from kivy.clock import Clock
from kivy.properties import StringProperty, NumericProperty, ObjectProperty
from app.controllers.product_controller import ProductController
from app.utils.helpers import format_currency
from app.utils.theme import UNITS, GST_RATES


class ProductCard(MDCard):
    product_id = NumericProperty(0)
    product_name = StringProperty("")
    sku = StringProperty("")
    price = StringProperty("")
    stock = StringProperty("")
    category = StringProperty("")
    stock_color = ObjectProperty((0.063, 0.725, 0.506, 1))


class ProductsScreen(MDScreen):
    """Product management screen."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.controller = ProductController()
        self.dialog = None
        self.edit_product_id = None
        self._category_menu = None
        self._all_categories = []

    def on_enter(self):
        Clock.schedule_once(self._load_products, 0.1)

    def _load_products(self, dt=None, search=None, category_id=None,
                       low_stock=False):
        products = self.controller.get_all_products(
            search=search, category_id=category_id, low_stock_only=low_stock)
        self._render_products(products)

    def _render_products(self, products):
        grid = self.ids.products_grid
        grid.clear_widgets()
        for p in products:
            qty = int(p.get("quantity", 0))
            min_s = int(p.get("min_stock", 5))
            color = (0.063, 0.725, 0.506, 1)
            if qty == 0:
                color = (0.937, 0.267, 0.267, 1)
            elif qty <= min_s:
                color = (0.969, 0.620, 0.039, 1)

            card = ProductCard()
            card.product_id = p["id"]
            card.product_name = p["name"]
            card.sku = p.get("sku") or p.get("product_code", "")
            card.price = format_currency(p.get("selling_price", 0))
            card.stock = f"Stock: {qty} {p.get('unit', 'pcs')}"
            card.category = p.get("category_name", "Uncategorized")
            card.stock_color = color
            card.bind(on_release=lambda x, pid=p["id"]: self.view_product(pid))
            grid.add_widget(card)

        self.ids.product_count_label.text = f"{len(products)} Products"

    def on_search(self, text):
        Clock.unschedule(self._search_debounce)
        self._search_debounce = Clock.schedule_once(
            lambda dt: self._load_products(search=text.strip() or None), 0.4)

    def open_add_dialog(self):
        self.edit_product_id = None
        self._show_product_dialog()

    def view_product(self, product_id):
        self.edit_product_id = product_id
        product = self.controller.get_product(product_id)
        self._show_product_dialog(product)

    def _show_product_dialog(self, product=None):
        content = ProductFormContent(
            product=product,
            categories=self.controller.get_categories(),
            controller=self.controller
        )
        self.dialog = MDDialog(
            title="Edit Product" if product else "Add Product",
            type="custom",
            content_cls=content,
            buttons=[
                MDFlatButton(text="CANCEL",
                             on_release=lambda x: self.dialog.dismiss()),
                MDRaisedButton(
                    text="SAVE",
                    on_release=lambda x: self._save_product(content)
                )
            ]
        )
        self.dialog.open()

    def _save_product(self, form):
        data = form.get_data()
        if not data:
            return
        if self.edit_product_id:
            result = self.controller.update_product(self.edit_product_id, data)
        else:
            result = self.controller.add_product(data)

        if result["success"]:
            self.dialog.dismiss()
            self._load_products()
            show_snackbar(result["message"])
        else:
            show_snackbar(f"Error: {result['message']}")

    def delete_product(self, product_id):
        def confirm(dialog_obj):
            self.controller.delete_product(product_id)
            dialog_obj.dismiss()
            self._load_products()
            show_snackbar("Product archived.")

        dialog = MDDialog(
            title="Archive Product",
            text="Are you sure you want to archive this product?",
            buttons=[
                MDFlatButton(text="CANCEL",
                             on_release=lambda x: dialog.dismiss()),
                MDRaisedButton(text="ARCHIVE",
                               on_release=lambda x: confirm(dialog))
            ]
        )
        dialog.open()

    def generate_barcode(self, product_id):
        result = self.controller.generate_barcode(product_id)
        msg = f"Barcode saved: {result.get('path', '')}" if result["success"] \
            else f"Error: {result['message']}"
        show_snackbar(msg)

    def generate_qr(self, product_id):
        result = self.controller.generate_qr_code(product_id)
        msg = "QR Code generated!" if result["success"] else f"Error: {result['message']}"
        show_snackbar(msg)

    def import_csv(self):
        from kivymd.uix.filemanager import MDFileManager
        self._file_manager = MDFileManager(
            exit_manager=lambda x: self._file_manager.close(),
            select_path=self._on_csv_selected,
            ext=[".csv"]
        )
        self._file_manager.show("/")

    def _on_csv_selected(self, path):
        self._file_manager.close()
        result = self.controller.import_from_csv(path)
        msg = f"Imported: {result['added']} | Skipped: {result['skipped']}"
        show_snackbar(msg)
        self._load_products()

    def export_csv(self):
        import os
        path = os.path.join("exports", "products_export.csv")
        os.makedirs("exports", exist_ok=True)
        result = self.controller.export_to_csv(path)
        show_snackbar(result["message"])

    def filter_low_stock(self):
        self._load_products(low_stock=True)


class ProductFormContent(MDBoxLayout):
    """Form widget for add/edit product dialog."""

    def __init__(self, product=None, categories=None, controller=None, **kwargs):
        super().__init__(**kwargs)
        self.orientation = "vertical"
        self.spacing = dp(8)
        self.padding = dp(8)
        self.size_hint_y = None
        self.height = dp(480)
        self.product = product
        self.categories = categories or []
        self.controller = controller
        self._build_form()

    def _build_form(self):
        p = self.product or {}
        fields_data = [
            ("name", "Product Name *", str(p.get("name", ""))),
            ("selling_price", "Selling Price *", str(p.get("selling_price", ""))),
            ("purchase_price", "Purchase Price", str(p.get("purchase_price", ""))),
            ("quantity", "Quantity", str(p.get("quantity", "0"))),
            ("min_stock", "Min Stock", str(p.get("min_stock", "5"))),
            ("expiry_date", "Expiry Date (YYYY-MM-DD)", str(p.get("expiry_date") or "")),
            ("sku", "SKU", str(p.get("sku", ""))),
            ("barcode", "Barcode (Leave blank to auto-generate)", str(p.get("barcode", ""))),
            ("brand", "Brand", str(p.get("brand", ""))),
            ("gst_rate", "GST Rate %", str(p.get("gst_rate", "0"))),
            ("discount", "Discount %", str(p.get("discount", "0"))),
        ]
        self._fields = {}
        scroll = MDScrollView()
        container = MDBoxLayout(
            orientation="vertical", spacing=dp(6),
            size_hint_y=None, padding=[dp(4), 0]
        )
        container.bind(minimum_height=container.setter("height"))
        for fid, hint, val in fields_data:
            tf = MDTextField(hint_text=hint, text=val,
                             size_hint_y=None, height=dp(48))
            self._fields[fid] = tf
            container.add_widget(tf)
        scroll.add_widget(container)
        self.add_widget(scroll)

    def get_data(self):
        data = {}
        for key, tf in self._fields.items():
            val = tf.text.strip()
            if key in ("selling_price", "purchase_price", "gst_rate", "discount",
                       "mrp"):
                try:
                    data[key] = float(val) if val else 0.0
                except ValueError:
                    data[key] = 0.0
            elif key in ("quantity", "min_stock", "max_stock"):
                try:
                    data[key] = int(val) if val else 0
                except ValueError:
                    data[key] = 0
            else:
                data[key] = val
        if not data.get("name"):
            show_snackbar("Product name is required.")
            return None
        return data


