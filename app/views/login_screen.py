"""
SmartPOS Pro - Splash & Login Screens  (KivyMD 1.2.0)
"""
from kivymd.uix.screen import MDScreen
from kivymd.uix.progressbar import MDProgressBar
from kivy.animation import Animation
from kivy.clock import Clock
from kivy.metrics import dp


class SplashScreen(MDScreen):
    def on_enter(self):
        self.ids.progress.value = 0
        anim = Animation(value=100, duration=2.0)
        anim.bind(on_complete=lambda *a: setattr(self.manager, "current", "login"))
        anim.start(self.ids.progress)


class LoginScreen(MDScreen):
    def on_enter(self):
        try:
            from app.utils.session import SessionManager
            token = SessionManager().get_saved_token()
            if token:
                from app.controllers.auth_controller import AuthController
                auth = AuthController()
                if auth.validate_session(token):
                    self._go_main(auth, auth.current_user)
        except Exception:
            pass

    def do_login(self):
        username = self.ids.username.text.strip()
        password = self.ids.password.text.strip()
        remember = False
        try:
            remember = self.ids.remember.active
        except Exception:
            pass

        if not username or not password:
            self.ids.error_label.text = "Enter username and password."
            return

        from app.controllers.auth_controller import AuthController
        auth   = AuthController()
        result = auth.login(username, password, remember)

        if result["success"]:
            if remember:
                from app.utils.session import SessionManager
                SessionManager().save_token(result["token"])
            self.ids.error_label.text = ""
            self._go_main(auth, result["user"])
        else:
            self.ids.error_label.text = result["message"]
            self._shake()

    def _go_main(self, auth, user):
        from kivy.app import App
        App.get_running_app().on_login_success(auth, user)

    def _shake(self):
        try:
            card = self.ids.login_card
            anim = (Animation(x=card.x+dp(8), d=0.05) +
                    Animation(x=card.x-dp(8), d=0.05) +
                    Animation(x=card.x+dp(4), d=0.05) +
                    Animation(x=card.x,       d=0.05))
            anim.start(card)
        except Exception:
            pass

    def toggle_password(self):
        tf = self.ids.password
        tf.password = not tf.password
        self.ids.eye_btn.icon = "eye-off" if tf.password else "eye"
