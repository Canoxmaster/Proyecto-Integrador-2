import customtkinter as ctk
from tkinter import messagebox
from .main_window import MainWindow
from .. import db
from . import theme

class Login(ctk.CTk):
    def __init__(self):
        theme.apply_global_theme()
        super().__init__()

        self.title("Acceso | Control de Visitas")
        self.geometry("1000x600")
        self.resizable(False, False)
        self.configure(fg_color=theme.APP_BG)

        container = ctk.CTkFrame(self, fg_color=theme.CARD_BG, corner_radius=20, border_width=1, border_color=theme.CARD_BORDER)
        container.place(relx=0.5, rely=0.5, anchor="center")

        header = ctk.CTkFrame(container, fg_color=theme.PRIMARY, corner_radius=18)
        header.pack(fill="x", padx=20, pady=(20, 12))

        title = ctk.CTkLabel(header, text="Control de Visitas", font=("Arial", 26, "bold"), text_color=theme.PRIMARY_TEXT)
        title.pack(pady=(18, 4))
        subtitle = ctk.CTkLabel(header, text="Inicia sesión para continuar", font=("Arial", 15), text_color=theme.PRIMARY_TEXT)
        subtitle.pack(pady=(0, 10))

        form = ctk.CTkFrame(container, fg_color=theme.CARD_BG)
        form.pack(fill="both", padx=32, pady=(0, 24))

        self.entry_user = ctk.CTkEntry(form, placeholder_text="Usuario", width=320, height=44, corner_radius=12,
                                       fg_color=theme.INPUT_BG, text_color=theme.TEXT_PRIMARY)
        self.entry_user.pack(pady=10)

        self.entry_pass = ctk.CTkEntry(form, placeholder_text="Contraseña", show="*", width=320, height=44, corner_radius=12,
                                       fg_color=theme.INPUT_BG, text_color=theme.TEXT_PRIMARY)
        self.entry_pass.pack(pady=10)

        # Autofill de pruebas
        try:
            self.entry_user.insert(0, "admin")
            self.entry_pass.insert(0, "1234")
        except Exception:
            pass

        btn = ctk.CTkButton(container, text="Ingresar", width=280, height=44, corner_radius=14,
                             fg_color=theme.PRIMARY, hover_color=theme.PRIMARY_HOVER,
                             text_color=theme.PRIMARY_TEXT, command=self.login)
        btn.pack(pady=(0, 28))

        self.bind('<Return>', lambda e: self.login())

    # Preparar DB y catálogos por defecto
    db.ensure_db_exists()
    db.ensure_default_admin()
    db.ensure_soft_delete_columns()
    db.ensure_default_catalogs()

    def login(self):
        user = self.entry_user.get().strip()
        pwd = self.entry_pass.get().strip()
        if not user or not pwd:
            messagebox.showwarning("Campos vacíos", "Ingresa usuario y contraseña")
            return
        user_id = db.authenticate(user, pwd)
        if not user_id:
            try:
                db.log_event("ADMIN", None, "LOGIN_FALLIDO", f"Usuario={user}")
            except Exception:
                pass
            messagebox.showerror("Acceso denegado", "Usuario o contraseña incorrectos")
            return
        try:
            db.log_event("ADMIN", user_id, "LOGIN_EXITOSO", f"Usuario={user}")
        except Exception:
            pass
        self.destroy()
        app = MainWindow(user_id=user_id, username=user)
        app.mainloop()
