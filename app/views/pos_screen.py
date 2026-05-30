"""
SmartPOS Pro - POS Billing Screen (KivyMD)
Full touch-optimized POS with cart, payments, discounts, invoice PDF.
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
from kivymd.uix.selectioncontrol import MDSwitch
from kivy.metrics import dp
from kivy.clock import Clock
from kivy.properties import StringProperty, NumericProperty, ListProperty
from app.controllers.billing_controller import BillingController
from app.controllers.product_controller import ProductController
from app.controllers.customer_controller import CustomerController
from app.utils.helpers import format_currency


class CartItem(MDBoxLayout):
    product_name = StringProperty("")
    price = StringProperty("")
    quantity = NumericProperty(1)
    total = StringProperty("")
    product_id = NumericProperty(0)


class POSScreen(MDScreen):
    """Touch-optimized POS billing screen."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.billing = BillingController()
        self.product_ctrl = ProductController()
        self.customer_ctrl = CustomerController()
        self.dialog = None
        self._last_invoice_id = None

    def on_enter(self):
        self.billing.clear_cart()
        self._load_products()
        self._update_cart_display()

    def _load_products(self, search=None, category_id=None):
        products = self.product_ctrl.get_all_products(search=search)
        grid = self.ids.product_grid
        grid.clear_widgets()
        for p in products[:50]:
            btn = MDRaisedButton(
                text=f"{p['name']}\n{format_currency(p['selling_price'])}",
                size_hint=(None, None),
                size=(dp(130), dp(60)),
                on_release=lambda x, pid=p["id"]: self.add_to_cart(pid)
            )
            grid.add_widget(btn)

    def on_search(self, text):
        Clock.unschedule(self._debounce)
        self._debounce = Clock.schedule_once(
            lambda dt: self._load_products(search=text.strip() or None), 0.35)

    def on_barcode_entered(self, barcode):
        if barcode.strip():
            result = self.billing.add_to_cart(barcode=barcode.strip())
            self.ids.barcode_field.text = ""
            self._handle_cart_result(result)

    def add_to_cart(self, product_id):
        result = self.billing.add_to_cart(product_id=product_id)
        self._handle_cart_result(result)

    def _handle_cart_result(self, result):
        if result["success"]:
            self._update_cart_display()
        else:
            show_snackbar(result["message"])

    def remove_from_cart(self, product_id):
        self.billing.remove_from_cart(product_id)
        self._update_cart_display()

    def update_quantity(self, product_id, qty_str):
        try:
            qty = int(qty_str)
            result = self.billing.update_cart_quantity(product_id, qty)
            if not result["success"]:
                show_snackbar(result["message"])
            self._update_cart_display()
        except ValueError:
            pass

    def apply_coupon(self):
        code = self.ids.coupon_field.text.strip()
        if not code:
            return
        result = self.billing.apply_coupon(code)
        if result["success"]:
            show_snackbar(f"Coupon applied! Discount: {format_currency(result['coupon']['discount_value'])}")
            self._update_cart_display()
        else:
            show_snackbar(result["message"])

    def set_customer(self):
        def search_customers(text):
            customers = self.customer_ctrl.get_all_customers(search=text)
            self._render_customer_list(customers, content)

        content = MDBoxLayout(orientation="vertical", spacing=dp(8),
                              size_hint_y=None, height=dp(300))
        search_tf = MDTextField(hint_text="Search customer by name/phone",
                                size_hint_y=None, height=dp(48))
        search_tf.bind(text=lambda inst, val: search_customers(val))
        self._cust_list = MDScrollView()
        self._cust_container = MDBoxLayout(
            orientation="vertical", spacing=dp(4),
            size_hint_y=None)
        self._cust_container.bind(
            minimum_height=self._cust_container.setter("height"))
        self._cust_list.add_widget(self._cust_container)
        content.add_widget(search_tf)
        content.add_widget(self._cust_list)
        search_customers("")

        self.dialog = MDDialog(
            title="Select Customer",
            type="custom",
            content_cls=content,
            buttons=[
                MDFlatButton(text="WALK-IN",
                             on_release=self._set_walkin),
                MDFlatButton(text="CLOSE",
                             on_release=lambda x: self.dialog.dismiss()),
            ]
        )
        self.dialog.open()

    def _render_customer_list(self, customers, content):
        self._cust_container.clear_widgets()
        for c in customers[:20]:
            btn = MDFlatButton(
                text=f"{c['name']} | {c.get('phone', '')}",
                size_hint_y=None, height=dp(40),
                on_release=lambda x, cid=c["id"], nm=c["name"]: self._select_customer(cid, nm)
            )
            self._cust_container.add_widget(btn)

    def _select_customer(self, customer_id, name):
        self.billing.set_customer(customer_id)
        self.ids.customer_label.text = f"👤 {name}"
        if self.dialog:
            self.dialog.dismiss()
        self._update_cart_display()

    def _set_walkin(self, *args):
        self.billing.current_customer = None
        self.ids.customer_label.text = "👤 Walk-in Customer"
        if self.dialog:
            self.dialog.dismiss()

    def _update_cart_display(self):
        summary = self.billing.get_cart_summary()
        cart_list = self.ids.cart_list
        cart_list.clear_widgets()

        for item in summary["items"]:
            row = MDBoxLayout(
                orientation="horizontal",
                size_hint_y=None, height=dp(56),
                spacing=dp(4), padding=[dp(4), dp(4)]
            )
            row.add_widget(MDLabel(
                text=item["product_name"],
                size_hint_x=0.35, font_style="Caption"
            ))
            qty_field = MDTextField(
                text=str(item["quantity"]),
                size_hint_x=0.15, size_hint_y=None, height=dp(40),
                input_filter="int"
            )
            pid = item["product_id"]
            qty_field.bind(text=lambda inst, val, p=pid: self.update_quantity(p, val))
            row.add_widget(qty_field)
            row.add_widget(MDLabel(
                text=format_currency(item["unit_price"]),
                size_hint_x=0.2, font_style="Caption"
            ))
            row.add_widget(MDLabel(
                text=format_currency(item["total_price"]),
                size_hint_x=0.2, font_style="Caption",
                theme_text_color="Custom",
                text_color=(0.063, 0.725, 0.506, 1)
            ))
            del_btn = MDIconButton(
                icon="delete", size_hint_x=0.1,
                theme_icon_color="Custom",
                icon_color=(0.937, 0.267, 0.267, 1),
                on_release=lambda x, p=pid: self.remove_from_cart(p)
            )
            row.add_widget(del_btn)
            cart_list.add_widget(row)

        self.ids.subtotal_label.text = format_currency(summary["subtotal"])
        self.ids.tax_label.text = format_currency(summary["total_gst"])
        self.ids.discount_label.text = format_currency(summary["coupon_discount"])
        self.ids.total_label.text = format_currency(summary["total"])
        self.ids.item_count.text = f"{summary['item_count']} items"

    def open_payment_dialog(self):
        summary = self.billing.get_cart_summary()
        if not summary["items"]:
            show_snackbar("Cart is empty.")
            return

        content = PaymentContent(total=summary["total"])
        self.dialog = MDDialog(
            title=f"Payment - {format_currency(summary['total'])}",
            type="custom",
            content_cls=content,
            buttons=[
                MDFlatButton(text="CANCEL",
                             on_release=lambda x: self.dialog.dismiss()),
                MDRaisedButton(text="CONFIRM PAYMENT",
                               on_release=lambda x: self._process_payment(content))
            ]
        )
        self.dialog.open()

    def _process_payment(self, payment_form):
        payment_data = payment_form.get_data()
        user_id = getattr(self.manager, "current_user", {}).get("id", 1)
        result = self.billing.create_invoice(payment_data, user_id)
        self.dialog.dismiss()

        if result["success"]:
            self._last_invoice_id = result["invoice_id"]
            self._update_cart_display()
            Clock.schedule_once(lambda dt: self._show_success_dialog(result), 0.2)
        else:
            show_snackbar(f"Error: {result['message']}")

    def _show_success_dialog(self, result):
        dialog = MDDialog(
            title="✅ Payment Successful",
            text=(f"Invoice #{result['invoice_number']}\n"
                  f"Total: {format_currency(result['total'])}\n"
                  f"Balance: {format_currency(result['balance'])}"),
            buttons=[
                MDFlatButton(text="CLOSE",
                             on_release=lambda x: dialog.dismiss()),
                MDRaisedButton(text="PRINT PDF",
                               on_release=lambda x, did=dialog: self._print_pdf(did))
            ]
        )
        dialog.open()

    def _print_pdf(self, dialog):
        dialog.dismiss()
        if self._last_invoice_id:
            result = self.billing.generate_invoice_pdf(self._last_invoice_id)
            if result["success"]:
                path = result.get("path", "")
                msg = f"PDF saved: {path}"
                import os, platform
                try:
                    if platform.system() == 'Darwin':
                        os.system(f'open "{path}"')
                    elif platform.system() == 'Windows':
                        os.startfile(os.path.abspath(path))
                    else:
                        os.system(f'xdg-open "{path}"')
                except Exception:
                    pass
            else:
                msg = f"PDF error: {result.get('message', '')}"
            Clock.schedule_once(lambda dt: show_snackbar(msg), 0.2)

    def clear_cart(self):
        self.billing.clear_cart()
        self.ids.customer_label.text = "👤 Walk-in Customer"
        self.ids.coupon_field.text = ""
        self._update_cart_display()

    def scan_barcode(self):
        from app.utils.helpers import BarcodeScanner
        scanner = BarcodeScanner(callback=self._on_barcode_scanned)
        scanner.start_scan()

    def _on_barcode_scanned(self, data, code_type):
        if data:
            Clock.schedule_once(lambda dt: self.on_barcode_entered(data), 0)
        else:
            show_snackbar("Camera not available. Enter barcode manually.")


class PaymentContent(MDBoxLayout):
    def __init__(self, total=0, **kwargs):
        super().__init__(**kwargs)
        self.orientation = "vertical"
        self.spacing = dp(10)
        self.padding = dp(8)
        self.size_hint_y = None
        self.height = dp(220)
        self.total = total
        self._build()

    def _build(self):
        methods = ["Cash", "Card", "UPI", "Wallet", "Split"]
        self._method = "Cash"

        method_box = MDBoxLayout(spacing=dp(6), size_hint_y=None, height=dp(50))
        for m in methods:
            btn = MDFlatButton(
                text=m, size_hint_y=None, height=dp(36),
                on_release=lambda x, mt=m: setattr(self, "_method", mt)
            )
            method_box.add_widget(btn)
        self.add_widget(method_box)

        self._amount_tf = MDTextField(
            hint_text="Amount Paid",
            text=str(self.total),
            input_filter="float",
            size_hint_y=None, height=dp(48)
        )
        self.add_widget(self._amount_tf)

        self._ref_tf = MDTextField(
            hint_text="Reference No. (optional)",
            size_hint_y=None, height=dp(48)
        )
        self.add_widget(self._ref_tf)

    def get_data(self):
        return {
            "method": self._method.lower(),
            "paid_amount": float(self._amount_tf.text or self.total),
            "reference_no": self._ref_tf.text.strip()
        }


