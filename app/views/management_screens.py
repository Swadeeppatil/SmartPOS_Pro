"""SmartPOS Pro - Remaining screens: Customers, Suppliers, Inventory, Employees, Expenses."""
from kivymd.uix.screen import MDScreen
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.label import MDLabel
from kivymd.uix.button import MDRaisedButton, MDFlatButton, MDIconButton
from kivymd.uix.textfield import MDTextField
from kivymd.uix.scrollview import MDScrollView
from kivymd.uix.dialog import MDDialog
from app.utils.compat import show_snackbar
from kivy.metrics import dp
from kivy.clock import Clock


class CustomersScreen(MDScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        from app.controllers.customer_controller import CustomerController
        self.ctrl = CustomerController()
        self.dialog = None
        self.edit_id = None

    def on_enter(self):
        Clock.schedule_once(lambda dt: self._load(), 0.1)

    def _load(self, search=None):
        customers = self.ctrl.get_all_customers(search=search)
        container = self.ids.list_container
        container.clear_widgets()
        for c in customers:
            row = self._make_row(c)
            container.add_widget(row)
        self.ids.count_label.text = f"{len(customers)} Customers"

    def _make_row(self, c):
        from app.utils.helpers import format_currency
        row = MDBoxLayout(orientation="horizontal", size_hint_y=None,
                          height=dp(56), spacing=dp(8), padding=[dp(8), dp(4)])
        row.add_widget(MDLabel(text=c["name"], size_hint_x=0.3))
        row.add_widget(MDLabel(text=c.get("phone", "-"), size_hint_x=0.25,
                               theme_text_color="Secondary"))
        row.add_widget(MDLabel(text=c.get("membership_type", "regular").title(),
                               size_hint_x=0.2, theme_text_color="Secondary"))
        row.add_widget(MDLabel(
            text=f"Pts: {c.get('reward_points', 0)}", size_hint_x=0.15,
            theme_text_color="Secondary"))
        row.add_widget(MDIconButton(
            icon="pencil", size_hint_x=0.1,
            on_release=lambda x, cid=c["id"]: self.open_edit(cid)))
        return row

    def on_search(self, text):
        Clock.unschedule(self._debounce) if hasattr(self, "_debounce") else None
        self._debounce = Clock.schedule_once(
            lambda dt: self._load(search=text.strip() or None), 0.4)

    def open_add(self):
        self.edit_id = None
        self._show_dialog()

    def open_edit(self, cid):
        self.edit_id = cid
        self._show_dialog(self.ctrl.get_customer(cid))

    def _show_dialog(self, data=None):
        d = data or {}
        fields = [
            ("name", "Name *", d.get("name", "")),
            ("phone", "Phone", d.get("phone", "")),
            ("email", "Email", d.get("email", "")),
            ("address", "Address", d.get("address", "")),
            ("city", "City", d.get("city", "")),
            ("gst_number", "GST Number", d.get("gst_number", "")),
            ("credit_limit", "Credit Limit", str(d.get("credit_limit", "0"))),
        ]
        content = GenericForm(fields)
        self.dialog = MDDialog(
            title="Edit Customer" if data else "Add Customer",
            type="custom", content_cls=content,
            buttons=[
                MDFlatButton(text="CANCEL", on_release=lambda x: self.dialog.dismiss()),
                MDRaisedButton(text="SAVE", on_release=lambda x: self._save(content))
            ])
        self.dialog.open()

    def _save(self, form):
        data = form.get_data()
        if self.edit_id:
            r = self.ctrl.update_customer(self.edit_id, data)
        else:
            r = self.ctrl.add_customer(data)
        self.dialog.dismiss()
        self._load()
        show_snackbar("Saved!" if r["success"] else r.get("message","Error"))


class SuppliersScreen(MDScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        from app.controllers.customer_controller import SupplierController
        self.ctrl = SupplierController()
        self.dialog = None
        self.edit_id = None

    def on_enter(self):
        Clock.schedule_once(lambda dt: self._load(), 0.1)

    def _load(self, search=None):
        suppliers = self.ctrl.get_all_suppliers(search=search)
        container = self.ids.list_container
        container.clear_widgets()
        for s in suppliers:
            row = MDBoxLayout(orientation="horizontal", size_hint_y=None,
                              height=dp(56), spacing=dp(8), padding=[dp(8), dp(4)])
            row.add_widget(MDLabel(text=s["name"], size_hint_x=0.3))
            row.add_widget(MDLabel(text=s.get("phone", "-"), size_hint_x=0.25,
                                   theme_text_color="Secondary"))
            row.add_widget(MDLabel(text=s.get("gst_number", "-"), size_hint_x=0.3,
                                   theme_text_color="Secondary"))
            row.add_widget(MDIconButton(
                icon="pencil", size_hint_x=0.15,
                on_release=lambda x, sid=s["id"]: self.open_edit(sid)))
            container.add_widget(row)
        self.ids.count_label.text = f"{len(suppliers)} Suppliers"

    def on_search(self, text):
        Clock.schedule_once(lambda dt: self._load(search=text.strip() or None), 0.4)

    def open_add(self):
        self.edit_id = None
        self._show_dialog()

    def open_edit(self, sid):
        self.edit_id = sid
        self._show_dialog(self.ctrl.get_supplier(sid))

    def _show_dialog(self, data=None):
        d = data or {}
        fields = [
            ("name", "Supplier Name *", d.get("name", "")),
            ("contact_person", "Contact Person", d.get("contact_person", "")),
            ("phone", "Phone", d.get("phone", "")),
            ("email", "Email", d.get("email", "")),
            ("address", "Address", d.get("address", "")),
            ("gst_number", "GST Number", d.get("gst_number", "")),
        ]
        content = GenericForm(fields)
        self.dialog = MDDialog(
            title="Edit Supplier" if data else "Add Supplier",
            type="custom", content_cls=content,
            buttons=[
                MDFlatButton(text="CANCEL", on_release=lambda x: self.dialog.dismiss()),
                MDRaisedButton(text="SAVE", on_release=lambda x: self._save(content))
            ])
        self.dialog.open()

    def _save(self, form):
        data = form.get_data()
        if self.edit_id:
            r = self.ctrl.update_supplier(self.edit_id, data)
        else:
            r = self.ctrl.add_supplier(data)
        self.dialog.dismiss()
        self._load()
        show_snackbar("Saved!" if r["success"] else r.get("message","Error"))


class InventoryScreen(MDScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        from app.controllers.product_controller import ProductController
        self.ctrl = ProductController()
        self.dialog = None

    def on_enter(self):
        Clock.schedule_once(lambda dt: self._load(), 0.1)

    def _load(self):
        from app.utils.helpers import format_currency
        value = self.ctrl.get_inventory_value()
        self.ids.inv_value.text = format_currency(value.get("selling_value") or 0)
        self.ids.total_products.text = str(value.get("total_products") or 0)
        self.ids.low_stock_count.text = str(value.get("low_stock") or 0)
        self.ids.out_stock_count.text = str(value.get("out_of_stock") or 0)
        self._load_transactions()

    def _load_transactions(self):
        from app.models.database import DatabaseManager
        db = DatabaseManager()
        txns = db.fetchall(
            """SELECT it.*, p.name as product_name
               FROM inventory_transactions it
               LEFT JOIN products p ON it.product_id=p.id
               ORDER BY it.created_at DESC LIMIT 50""")
        container = self.ids.txn_list
        container.clear_widgets()
        for t in txns:
            row = MDBoxLayout(orientation="horizontal", size_hint_y=None,
                              height=dp(48), spacing=dp(8), padding=[dp(8), dp(4)])
            row.add_widget(MDLabel(text=t.get("product_name",""), size_hint_x=0.35))
            row.add_widget(MDLabel(text=t.get("transaction_type","").replace("_"," ").title(),
                                   size_hint_x=0.25, theme_text_color="Secondary"))
            qty = int(t.get("quantity", 0))
            row.add_widget(MDLabel(
                text=f"+{qty}" if "purchase" in str(t.get("transaction_type","")) else f"-{qty}",
                size_hint_x=0.15,
                theme_text_color="Custom",
                text_color=(0.063, 0.725, 0.506, 1) if qty >= 0 else (0.937, 0.267, 0.267, 1)))
            row.add_widget(MDLabel(text=str(t.get("created_at",""))[:10],
                                   size_hint_x=0.25, theme_text_color="Secondary"))
            container.add_widget(row)

    def open_stock_in(self):
        self._show_stock_dialog("stock_in")

    def open_stock_out(self):
        self._show_stock_dialog("stock_out")

    def _show_stock_dialog(self, txn_type):
        fields = [
            ("product_id", "Product ID", ""),
            ("quantity", "Quantity", ""),
            ("notes", "Notes", ""),
        ]
        content = GenericForm(fields)
        self.dialog = MDDialog(
            title="Stock In" if txn_type == "stock_in" else "Stock Out",
            type="custom", content_cls=content,
            buttons=[
                MDFlatButton(text="CANCEL", on_release=lambda x: self.dialog.dismiss()),
                MDRaisedButton(text="CONFIRM",
                               on_release=lambda x: self._process_stock(content, txn_type))
            ])
        self.dialog.open()

    def _process_stock(self, form, txn_type):
        data = form.get_data()
        try:
            pid = int(data.get("product_id", 0))
            qty = int(data.get("quantity", 0))
            if txn_type == "stock_out":
                qty = -qty
            user_id = getattr(self.manager, "current_user", {}).get("id", 1) if self.manager else 1
            r = self.ctrl.update_stock(pid, qty, txn_type, data.get("notes",""), user_id)
            self.dialog.dismiss()
            self._load()
            show_snackbar("Stock updated!" if r["success"] else r["message"])
        except ValueError:
            show_snackbar("Invalid product ID or quantity.")


class EmployeesScreen(MDScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        from app.controllers.expense_employee_controller import EmployeeController
        self.ctrl = EmployeeController()
        self.dialog = None
        self.edit_id = None

    def on_enter(self):
        Clock.schedule_once(lambda dt: self._load(), 0.1)

    def _load(self, search=None):
        employees = self.ctrl.get_all_employees(search=search)
        container = self.ids.list_container
        container.clear_widgets()
        for e in employees:
            row = MDBoxLayout(orientation="horizontal", size_hint_y=None,
                              height=dp(56), spacing=dp(8), padding=[dp(8), dp(4)])
            row.add_widget(MDLabel(text=e["full_name"], size_hint_x=0.3))
            row.add_widget(MDLabel(text=e.get("emp_code",""), size_hint_x=0.2,
                                   theme_text_color="Secondary"))
            row.add_widget(MDLabel(text=e.get("designation",""), size_hint_x=0.25,
                                   theme_text_color="Secondary"))
            from app.utils.helpers import format_currency
            row.add_widget(MDLabel(
                text=format_currency(e.get("salary",0)), size_hint_x=0.15))
            action_box = MDBoxLayout(size_hint_x=0.1, spacing=dp(2))
            action_box.add_widget(MDIconButton(
                icon="check-circle-outline", size_hint=(None, None), size=(dp(32),dp(32)),
                on_release=lambda x, eid=e["id"]: self._check_in(eid)))
            action_box.add_widget(MDIconButton(
                icon="clock-out", size_hint=(None, None), size=(dp(32),dp(32)),
                on_release=lambda x, eid=e["id"]: self._check_out(eid)))
            row.add_widget(action_box)
            container.add_widget(row)
        self.ids.count_label.text = f"{len(employees)} Employees"

    def open_add(self):
        self.edit_id = None
        self._show_dialog()

    def open_edit(self, eid):
        self.edit_id = eid
        self._show_dialog(self.ctrl.get_employee(eid))

    def _show_dialog(self, data=None):
        d = data or {}
        fields = [
            ("full_name", "Full Name *", d.get("full_name", "")),
            ("phone", "Phone", d.get("phone", "")),
            ("email", "Email", d.get("email", "")),
            ("department", "Department", d.get("department", "")),
            ("designation", "Designation", d.get("designation", "")),
            ("salary", "Salary", str(d.get("salary", ""))),
        ]
        content = GenericForm(fields)
        self.dialog = MDDialog(
            title="Edit Employee" if data else "Add Employee",
            type="custom", content_cls=content,
            buttons=[
                MDFlatButton(text="CANCEL", on_release=lambda x: self.dialog.dismiss()),
                MDRaisedButton(text="SAVE", on_release=lambda x: self._save(content))
            ])
        self.dialog.open()

    def _save(self, form):
        data = form.get_data()
        if self.edit_id:
            r = self.ctrl.update_employee(self.edit_id, data)
        else:
            r = self.ctrl.add_employee(data)
        self.dialog.dismiss()
        self._load()
        show_snackbar("Saved!" if r["success"] else r.get("message","Error"))

    def _check_in(self, eid):
        r = self.ctrl.check_in(eid)
        show_snackbar(r.get("message","Checked in!"))

    def _check_out(self, eid):
        r = self.ctrl.check_out(eid)
        msg = f"Checked out! Hours: {r.get('hours_worked',0)}" if r["success"] else r["message"]
        show_snackbar(msg)


class ExpensesScreen(MDScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        from app.controllers.expense_employee_controller import ExpenseController
        self.ctrl = ExpenseController()
        self.dialog = None

    def on_enter(self):
        Clock.schedule_once(lambda dt: self._load(), 0.1)

    def _load(self):
        from app.utils.helpers import format_currency
        total = self.ctrl.get_total_expenses("month")
        self.ids.total_expense.text = format_currency(total)
        expenses = self.ctrl.get_expenses()
        container = self.ids.list_container
        container.clear_widgets()
        for e in expenses:
            row = MDBoxLayout(orientation="horizontal", size_hint_y=None,
                              height=dp(52), spacing=dp(8), padding=[dp(8), dp(4)])
            row.add_widget(MDLabel(text=e.get("title",""), size_hint_x=0.35))
            row.add_widget(MDLabel(text=e.get("category_name",""), size_hint_x=0.25,
                                   theme_text_color="Secondary"))
            row.add_widget(MDLabel(text=format_currency(e.get("amount",0)),
                                   size_hint_x=0.2,
                                   theme_text_color="Custom",
                                   text_color=(0.937, 0.267, 0.267, 1)))
            row.add_widget(MDLabel(text=str(e.get("expense_date",""))[:10],
                                   size_hint_x=0.2, theme_text_color="Secondary"))
            container.add_widget(row)

    def open_add(self):
        categories = self.ctrl.get_expense_categories()
        cat_names = [c["name"] for c in categories]
        cat_ids = {c["name"]: c["id"] for c in categories}
        fields = [
            ("title", "Title *", ""),
            ("amount", "Amount *", ""),
            ("notes", "Notes", ""),
        ]
        content = GenericForm(fields, dropdowns={"category": cat_names})
        self.dialog = MDDialog(
            title="Add Expense",
            type="custom", content_cls=content,
            buttons=[
                MDFlatButton(text="CANCEL", on_release=lambda x: self.dialog.dismiss()),
                MDRaisedButton(text="SAVE",
                               on_release=lambda x: self._save(content, cat_ids))
            ])
        self.dialog.open()

    def _save(self, form, cat_ids):
        data = form.get_data()
        cat_name = data.pop("category", None)
        if cat_name and cat_name in cat_ids:
            data["category_id"] = cat_ids[cat_name]
        user_id = getattr(self.manager, "current_user", {}).get("id", 1) if self.manager else 1
        r = self.ctrl.add_expense(data, user_id)
        self.dialog.dismiss()
        self._load()
        show_snackbar("Expense added!" if r["success"] else r.get("message","Error"))


class GenericForm(MDBoxLayout):
    """Reusable form with text fields."""
    def __init__(self, fields, dropdowns=None, **kwargs):
        super().__init__(**kwargs)
        self.orientation = "vertical"
        self.spacing = dp(6)
        self.padding = dp(8)
        self.size_hint_y = None
        self.height = dp(max(300, len(fields) * 58 + 20))
        self._fields = {}
        self._dropdowns = {}
        scroll = MDScrollView()
        container = MDBoxLayout(orientation="vertical", spacing=dp(4), size_hint_y=None)
        container.bind(minimum_height=container.setter("height"))
        for fid, hint, val in fields:
            tf = MDTextField(hint_text=hint, text=str(val),
                             size_hint_y=None, height=dp(48))
            self._fields[fid] = tf
            container.add_widget(tf)
        scroll.add_widget(container)
        self.add_widget(scroll)

    def get_data(self):
        return {k: tf.text.strip() for k, tf in self._fields.items()}


