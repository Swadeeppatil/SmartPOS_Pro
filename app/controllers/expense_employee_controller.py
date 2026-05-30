"""
SmartPOS Pro - Expense & Employee Controllers
"""
import logging
from datetime import datetime, date
from app.models.database import DatabaseManager

logger = logging.getLogger(__name__)


class ExpenseController:
    def __init__(self):
        self.db = DatabaseManager()

    def add_expense(self, data: dict, user_id: int):
        if not data.get("title") or not data.get("amount"):
            return {"success": False, "message": "Title and amount required."}
        try:
            eid = self.db.execute(
                """INSERT INTO expenses
                   (category_id, title, amount, expense_date,
                    payment_method, reference_no, notes, user_id)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (data.get("category_id"), data["title"],
                 float(data["amount"]),
                 data.get("expense_date", datetime.now().strftime("%Y-%m-%d")),
                 data.get("payment_method", "cash"),
                 data.get("reference_no"), data.get("notes"), user_id)
            )
            return {"success": True, "expense_id": eid}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def update_expense(self, eid: int, data: dict):
        self.db.execute(
            """UPDATE expenses SET category_id=?,title=?,amount=?,
               expense_date=?,payment_method=?,notes=? WHERE id=?""",
            (data.get("category_id"), data["title"], float(data["amount"]),
             data.get("expense_date"), data.get("payment_method","cash"),
             data.get("notes"), eid)
        )
        return {"success": True}

    def delete_expense(self, eid: int):
        self.db.execute("DELETE FROM expenses WHERE id=?", (eid,))
        return {"success": True}

    def get_expenses(self, date_from=None, date_to=None, category_id=None):
        conditions = ["1=1"]
        params = []
        if date_from:
            conditions.append("DATE(e.expense_date) >= ?")
            params.append(date_from)
        if date_to:
            conditions.append("DATE(e.expense_date) <= ?")
            params.append(date_to)
        if category_id:
            conditions.append("e.category_id=?")
            params.append(category_id)
        where = " AND ".join(conditions)
        return self.db.fetchall(
            f"""SELECT e.*, ec.name as category_name
                FROM expenses e
                LEFT JOIN expense_categories ec ON e.category_id=ec.id
                WHERE {where} ORDER BY e.expense_date DESC""",
            params)

    def get_expense_summary(self, period="month"):
        now = datetime.now()
        if period == "month":
            date_from = now.strftime("%Y-%m-01")
        elif period == "year":
            date_from = now.strftime("%Y-01-01")
        else:
            date_from = now.strftime("%Y-%m-%d")

        return self.db.fetchall(
            """SELECT ec.name as category,
               SUM(e.amount) as total,
               COUNT(*) as count
               FROM expenses e
               LEFT JOIN expense_categories ec ON e.category_id=ec.id
               WHERE DATE(e.expense_date) >= ?
               GROUP BY e.category_id ORDER BY total DESC""",
            (date_from,))

    def get_total_expenses(self, period="month"):
        now = datetime.now()
        if period == "month":
            df = now.strftime("%Y-%m-01")
            dt = now.strftime("%Y-%m-%d")
        elif period == "year":
            df = now.strftime("%Y-01-01")
            dt = now.strftime("%Y-%m-%d")
        else:
            df = dt = now.strftime("%Y-%m-%d")
        result = self.db.fetchone(
            """SELECT SUM(amount) as total FROM expenses
               WHERE DATE(expense_date) BETWEEN ? AND ?""",
            (df, dt))
        return float(result["total"] or 0) if result else 0

    def get_expense_categories(self):
        return self.db.fetchall("SELECT * FROM expense_categories ORDER BY name")


class EmployeeController:
    def __init__(self):
        self.db = DatabaseManager()

    def add_employee(self, data: dict):
        if not data.get("full_name"):
            return {"success": False, "message": "Employee name required."}
        try:
            emp_code = self._generate_emp_code()
            eid = self.db.execute(
                """INSERT INTO employees
                   (emp_code, full_name, phone, email, address,
                    department, designation, date_of_join, salary)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (emp_code, data["full_name"], data.get("phone"),
                 data.get("email"), data.get("address"),
                 data.get("department"), data.get("designation"),
                 data.get("date_of_join",
                           datetime.now().strftime("%Y-%m-%d")),
                 float(data.get("salary", 0)))
            )
            return {"success": True, "employee_id": eid, "emp_code": emp_code}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def update_employee(self, eid: int, data: dict):
        self.db.execute(
            """UPDATE employees SET full_name=?,phone=?,email=?,address=?,
               department=?,designation=?,salary=?,updated_at=? WHERE id=?""",
            (data["full_name"], data.get("phone"), data.get("email"),
             data.get("address"), data.get("department"),
             data.get("designation"), float(data.get("salary", 0)),
             datetime.now().isoformat(), eid)
        )
        return {"success": True}

    def delete_employee(self, eid: int):
        self.db.execute(
            "UPDATE employees SET is_active=0 WHERE id=?", (eid,))
        return {"success": True}

    def get_all_employees(self, search=None):
        if search:
            term = f"%{search}%"
            return self.db.fetchall(
                """SELECT * FROM employees WHERE is_active=1
                   AND (full_name LIKE ? OR emp_code LIKE ? OR department LIKE ?)
                   ORDER BY full_name""",
                (term, term, term))
        return self.db.fetchall(
            "SELECT * FROM employees WHERE is_active=1 ORDER BY full_name")

    def get_employee(self, eid: int):
        return self.db.fetchone(
            "SELECT * FROM employees WHERE id=?", (eid,))

    # Attendance
    def check_in(self, employee_id: int):
        today = date.today().isoformat()
        existing = self.db.fetchone(
            """SELECT * FROM attendance
               WHERE employee_id=? AND attendance_date=?""",
            (employee_id, today))
        if existing:
            return {"success": False,
                    "message": "Already checked in today."}
        now = datetime.now().strftime("%H:%M:%S")
        self.db.execute(
            """INSERT INTO attendance
               (employee_id, attendance_date, check_in, status)
               VALUES (?,?,?,?)""",
            (employee_id, today, now, "present"))
        return {"success": True, "check_in": now}

    def check_out(self, employee_id: int):
        today = date.today().isoformat()
        record = self.db.fetchone(
            """SELECT * FROM attendance
               WHERE employee_id=? AND attendance_date=?""",
            (employee_id, today))
        if not record:
            return {"success": False, "message": "No check-in found for today."}
        if record.get("check_out"):
            return {"success": False, "message": "Already checked out."}

        now = datetime.now()
        now_str = now.strftime("%H:%M:%S")
        check_in_dt = datetime.strptime(
            f"{today} {record['check_in']}", "%Y-%m-%d %H:%M:%S")
        hours = round((now - check_in_dt).total_seconds() / 3600, 2)
        overtime = max(0, hours - 8)

        self.db.execute(
            """UPDATE attendance SET check_out=?, hours_worked=?,
               overtime_hours=? WHERE id=?""",
            (now_str, hours, overtime, record["id"]))
        return {"success": True, "check_out": now_str, "hours_worked": hours}

    def get_attendance(self, employee_id=None, month=None, year=None):
        conditions = ["1=1"]
        params = []
        if employee_id:
            conditions.append("a.employee_id=?")
            params.append(employee_id)
        if month and year:
            conditions.append("strftime('%m', a.attendance_date)=?")
            conditions.append("strftime('%Y', a.attendance_date)=?")
            params.extend([f"{month:02d}", str(year)])
        where = " AND ".join(conditions)
        return self.db.fetchall(
            f"""SELECT a.*, e.full_name, e.emp_code
                FROM attendance a
                LEFT JOIN employees e ON a.employee_id=e.id
                WHERE {where} ORDER BY a.attendance_date DESC""",
            params)

    # Payroll
    def generate_payroll(self, employee_id: int, month: str, user_id: int):
        """Calculate and generate payroll for an employee."""
        employee = self.get_employee(employee_id)
        if not employee:
            return {"success": False, "message": "Employee not found."}

        year, mon = month.split("-")
        attendance = self.get_attendance(employee_id, int(mon), int(year))
        working_days = len([a for a in attendance if a["status"] == "present"])
        total_hours = sum(a.get("hours_worked", 0) or 0 for a in attendance)
        overtime_hours = sum(a.get("overtime_hours", 0) or 0 for a in attendance)

        basic = float(employee.get("salary", 0))
        per_day = basic / 26
        earned = per_day * working_days
        overtime_pay = overtime_hours * (basic / 26 / 8) * 1.5
        net_salary = round(earned + overtime_pay, 2)

        existing = self.db.fetchone(
            "SELECT id FROM payroll WHERE employee_id=? AND month=?",
            (employee_id, month))
        if existing:
            return {"success": False, "message": "Payroll already generated."}

        pid = self.db.execute(
            """INSERT INTO payroll
               (employee_id, month, basic_salary, allowances,
                deductions, net_salary, status)
               VALUES (?,?,?,?,?,?,?)""",
            (employee_id, month, basic, overtime_pay, 0, net_salary, "pending")
        )
        return {
            "success": True,
            "payroll_id": pid,
            "net_salary": net_salary,
            "working_days": working_days,
            "overtime_hours": overtime_hours
        }

    def get_payroll(self, employee_id=None, month=None):
        conditions = ["1=1"]
        params = []
        if employee_id:
            conditions.append("p.employee_id=?")
            params.append(employee_id)
        if month:
            conditions.append("p.month=?")
            params.append(month)
        where = " AND ".join(conditions)
        return self.db.fetchall(
            f"""SELECT p.*, e.full_name, e.emp_code
                FROM payroll p LEFT JOIN employees e ON p.employee_id=e.id
                WHERE {where} ORDER BY p.month DESC""",
            params)

    def _generate_emp_code(self):
        last = self.db.fetchone(
            "SELECT emp_code FROM employees ORDER BY id DESC LIMIT 1")
        if last and last["emp_code"]:
            try:
                num = int(last["emp_code"].replace("EMP", "")) + 1
            except ValueError:
                num = 1001
        else:
            num = 1001
        return f"EMP{num:04d}"

