"""
SmartPOS Pro - Authentication Controller
Handles login, logout, session management, role-based permissions.
"""

import hashlib
import secrets
import logging
from datetime import datetime, timedelta
from app.models.database import DatabaseManager

logger = logging.getLogger(__name__)

# Role permission matrix
PERMISSIONS = {
    "admin": [
        "dashboard", "products", "pos", "inventory", "customers",
        "suppliers", "employees", "expenses", "reports", "settings",
        "analytics", "backup", "users"
    ],
    "manager": [
        "dashboard", "products", "pos", "inventory", "customers",
        "suppliers", "expenses", "reports", "analytics"
    ],
    "cashier": [
        "dashboard", "pos", "customers", "products_view"
    ],
    "staff": [
        "dashboard", "inventory", "products_view"
    ]
}

MAX_FAILED_ATTEMPTS = 5
LOCK_DURATION_MINUTES = 30
SESSION_DURATION_HOURS = 24


class AuthController:
    """Authentication and session management controller."""

    def __init__(self):
        self.db = DatabaseManager()
        self.current_user = None
        self.current_session = None

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def login(self, username: str, password: str, remember: bool = False):
        """
        Authenticate a user.
        Returns dict with success status, user data, and message.
        """
        username = username.strip().lower()

        if not username or not password:
            return {"success": False, "message": "Username and password required."}

        user = self.db.fetchone(
            "SELECT * FROM users WHERE username=? AND is_active=1",
            (username,)
        )

        if not user:
            self._log_failed_login(username)
            return {"success": False, "message": "Invalid credentials."}

        # Check account lock
        if user.get("locked_until"):
            lock_time = datetime.fromisoformat(user["locked_until"])
            if datetime.now() < lock_time:
                remaining = int((lock_time - datetime.now()).total_seconds() / 60)
                return {
                    "success": False,
                    "message": f"Account locked. Try again in {remaining} minutes."
                }
            else:
                # Unlock account
                self.db.execute(
                    "UPDATE users SET locked_until=NULL, failed_attempts=0 WHERE id=?",
                    (user["id"],)
                )

        # Verify password
        pwd_hash = hashlib.sha256(password.encode()).hexdigest()
        if pwd_hash != user["password_hash"]:
            return self._handle_failed_attempt(user)

        # Successful login
        self._reset_failed_attempts(user["id"])
        session_token = self._create_session(user["id"], remember)

        self.current_user = dict(user)
        self.current_session = session_token

        # Update last login
        self.db.execute(
            "UPDATE users SET last_login=? WHERE id=?",
            (datetime.now().isoformat(), user["id"])
        )

        # Log login history
        self.db.execute(
            "INSERT INTO login_history (user_id, status) VALUES (?, ?)",
            (user["id"], "success")
        )

        # Log activity
        self._log_activity(user["id"], "LOGIN", "auth", f"User {username} logged in")

        return {
            "success": True,
            "message": f"Welcome, {user['full_name']}!",
            "user": dict(user),
            "token": session_token,
            "permissions": self.get_permissions(user["role"])
        }

    def logout(self):
        """Log out the current user."""
        if self.current_user:
            user_id = self.current_user["id"]
            # Mark session inactive
            if self.current_session:
                self.db.execute(
                    "UPDATE sessions SET is_active=0 WHERE token=?",
                    (self.current_session,)
                )
            # Update login history
            self.db.execute(
                """UPDATE login_history SET logout_time=?
                   WHERE user_id=? AND logout_time IS NULL""",
                (datetime.now().isoformat(), user_id)
            )
            self._log_activity(user_id, "LOGOUT", "auth",
                               f"User {self.current_user['username']} logged out")
            self.current_user = None
            self.current_session = None
        return {"success": True, "message": "Logged out successfully."}

    def validate_session(self, token: str):
        """Validate a session token and restore current user."""
        if not token:
            return False
        session = self.db.fetchone(
            """SELECT s.*, u.* FROM sessions s
               JOIN users u ON s.user_id = u.id
               WHERE s.token=? AND s.is_active=1 AND u.is_active=1""",
            (token,)
        )
        if not session:
            return False

        # Check expiry
        if session.get("expires_at"):
            exp = datetime.fromisoformat(session["expires_at"])
            if datetime.now() > exp:
                self.db.execute(
                    "UPDATE sessions SET is_active=0 WHERE token=?", (token,))
                return False

        self.current_user = {
            "id": session["user_id"],
            "username": session["username"],
            "full_name": session["full_name"],
            "role": session["role"],
            "email": session["email"],
        }
        self.current_session = token
        return True

    # ------------------------------------------------------------------
    # User Management
    # ------------------------------------------------------------------

    def create_user(self, data: dict):
        """Create a new user account."""
        required = ["username", "password", "full_name", "role"]
        for field in required:
            if not data.get(field):
                return {"success": False, "message": f"{field} is required."}

        existing = self.db.fetchone(
            "SELECT id FROM users WHERE username=?", (data["username"].lower(),))
        if existing:
            return {"success": False, "message": "Username already exists."}

        pwd_hash = hashlib.sha256(data["password"].encode()).hexdigest()
        user_id = self.db.execute(
            """INSERT INTO users (username, password_hash, full_name, role, email, phone)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (data["username"].lower(), pwd_hash, data["full_name"],
             data["role"], data.get("email", ""), data.get("phone", ""))
        )
        if self.current_user:
            self._log_activity(self.current_user["id"], "CREATE_USER", "users",
                               f"Created user: {data['username']}")
        return {"success": True, "message": "User created successfully.", "user_id": user_id}

    def change_password(self, user_id: int, old_password: str, new_password: str):
        """Change a user's password."""
        user = self.db.fetchone("SELECT * FROM users WHERE id=?", (user_id,))
        if not user:
            return {"success": False, "message": "User not found."}

        old_hash = hashlib.sha256(old_password.encode()).hexdigest()
        if old_hash != user["password_hash"]:
            return {"success": False, "message": "Incorrect current password."}

        new_hash = hashlib.sha256(new_password.encode()).hexdigest()
        self.db.execute(
            "UPDATE users SET password_hash=?, updated_at=? WHERE id=?",
            (new_hash, datetime.now().isoformat(), user_id)
        )
        return {"success": True, "message": "Password changed successfully."}

    def get_all_users(self):
        """Retrieve all users."""
        return self.db.fetchall(
            "SELECT id, username, full_name, role, email, is_active, last_login FROM users"
        )

    def update_user(self, user_id: int, data: dict):
        """Update user details."""
        self.db.execute(
            """UPDATE users SET full_name=?, role=?, email=?, phone=?, updated_at=?
               WHERE id=?""",
            (data["full_name"], data["role"], data.get("email", ""),
             data.get("phone", ""), datetime.now().isoformat(), user_id)
        )
        return {"success": True, "message": "User updated."}

    def toggle_user_status(self, user_id: int):
        """Toggle user active/inactive status."""
        user = self.db.fetchone(
            "SELECT is_active FROM users WHERE id=?", (user_id,))
        if user:
            new_status = 0 if user["is_active"] else 1
            self.db.execute(
                "UPDATE users SET is_active=? WHERE id=?", (new_status, user_id))
        return {"success": True}

    # ------------------------------------------------------------------
    # Permissions
    # ------------------------------------------------------------------

    def get_permissions(self, role: str):
        """Return list of permitted modules for a given role."""
        return PERMISSIONS.get(role, [])

    def has_permission(self, module: str):
        """Check if current user has permission for a module."""
        if not self.current_user:
            return False
        role = self.current_user.get("role", "staff")
        return module in PERMISSIONS.get(role, [])

    # ------------------------------------------------------------------
    # Activity Logging
    # ------------------------------------------------------------------

    def _log_activity(self, user_id, action, module, details):
        try:
            self.db.execute(
                """INSERT INTO activity_logs (user_id, action, module, details)
                   VALUES (?, ?, ?, ?)""",
                (user_id, action, module, details)
            )
        except Exception as e:
            logger.error(f"Activity log error: {e}")

    def get_activity_logs(self, limit=100, user_id=None):
        """Retrieve recent activity logs."""
        if user_id:
            return self.db.fetchall(
                """SELECT al.*, u.username FROM activity_logs al
                   LEFT JOIN users u ON al.user_id=u.id
                   WHERE al.user_id=? ORDER BY al.created_at DESC LIMIT ?""",
                (user_id, limit)
            )
        return self.db.fetchall(
            """SELECT al.*, u.username FROM activity_logs al
               LEFT JOIN users u ON al.user_id=u.id
               ORDER BY al.created_at DESC LIMIT ?""",
            (limit,)
        )

    # ------------------------------------------------------------------
    # Private Helpers
    # ------------------------------------------------------------------

    def _create_session(self, user_id: int, remember: bool = False):
        token = secrets.token_hex(32)
        expires = None
        if remember:
            expires = (datetime.now() + timedelta(days=30)).isoformat()
        else:
            expires = (datetime.now() + timedelta(hours=SESSION_DURATION_HOURS)).isoformat()

        self.db.execute(
            "INSERT INTO sessions (user_id, token, expires_at) VALUES (?, ?, ?)",
            (user_id, token, expires)
        )
        return token

    def _handle_failed_attempt(self, user: dict):
        attempts = (user.get("failed_attempts") or 0) + 1
        if attempts >= MAX_FAILED_ATTEMPTS:
            lock_until = (
                datetime.now() + timedelta(minutes=LOCK_DURATION_MINUTES)
            ).isoformat()
            self.db.execute(
                "UPDATE users SET failed_attempts=?, locked_until=? WHERE id=?",
                (attempts, lock_until, user["id"])
            )
            return {
                "success": False,
                "message": f"Account locked for {LOCK_DURATION_MINUTES} minutes after too many failed attempts."
            }
        self.db.execute(
            "UPDATE users SET failed_attempts=? WHERE id=?",
            (attempts, user["id"])
        )
        remaining = MAX_FAILED_ATTEMPTS - attempts
        return {
            "success": False,
            "message": f"Invalid credentials. {remaining} attempts remaining."
        }

    def _reset_failed_attempts(self, user_id: int):
        self.db.execute(
            "UPDATE users SET failed_attempts=0, locked_until=NULL WHERE id=?",
            (user_id,)
        )

    def _log_failed_login(self, username: str):
        logger.warning(f"Failed login attempt for username: {username}")

