"""SmartPOS Pro - Session persistence helper."""
import os, json

SESSION_FILE = "smartpos_session.json"

class SessionManager:
    def save_token(self, token: str):
        with open(SESSION_FILE, "w") as f:
            json.dump({"token": token}, f)

    def get_saved_token(self):
        if os.path.exists(SESSION_FILE):
            try:
                with open(SESSION_FILE) as f:
                    return json.load(f).get("token")
            except Exception:
                pass
        return None

    def clear(self):
        if os.path.exists(SESSION_FILE):
            os.remove(SESSION_FILE)
