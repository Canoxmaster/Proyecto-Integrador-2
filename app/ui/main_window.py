from typing import Dict
import customtkinter as ctk
from tkinter import messagebox
from .. import db
from ..camera import camera
from . import theme
from .pages.dashboard import DashboardPage
from .pages.empresas import EmpresasPage
from .pages.areas import AreasPage
from .pages.motivos import MotivosPage
from .pages.personas import PersonasPage
from .pages.visitas import VisitasPage
from .pages.dispositivos import DispositivosPage
from .pages.reconocimientos import ReconocimientosPage
from .pages.eventos import EventosPage
from .pages.sesiones import SesionesPage


class MainWindow(ctk.CTk):
    def __init__(self, user_id: int, username: str):
        theme.apply_global_theme()
        super().__init__()
        self.user_id = user_id
        self.username = username

        self.title("Control de Visitas")
        self.geometry("1400x820")
        self.resizable(True, True)
        self.minsize(1100, 700)
        self.configure(fg_color=theme.APP_BG)

        # Layout
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Sidebar
        self.sidebar = ctk.CTkFrame(
            self,
            width=260,
            fg_color=theme.SIDEBAR_BG,
            corner_radius=0,
            border_width=1,
            border_color=theme.SIDEBAR_BORDER,
        )
        self.sidebar.grid(row=0, column=0, sticky="nsw")
        self.sidebar.grid_propagate(False)

        self.content = ctk.CTkFrame(self, corner_radius=0, fg_color=theme.APP_BG)
        self.content.grid(row=0, column=1, sticky="nsew")
        self.content.grid_propagate(False)
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_rowconfigure(0, weight=1)

        self._nav_buttons: Dict[str, ctk.CTkButton] = {}

        self._build_sidebar()

        # Default view
        self.current_page = None
        self.show_page("Dashboard")

    def _build_sidebar(self):
        header = ctk.CTkFrame(self.sidebar, fg_color=theme.TRANSPARENT)
        header.pack(fill="x", padx=18, pady=(24, 18))
        ctk.CTkLabel(header, text="Control de Visitas", font=("Arial", 18, "bold"), text_color=theme.SIDEBAR_TEXT).pack(anchor="w")
        ctk.CTkLabel(header, text=f"Usuario: {self.username}", font=("Arial", 14), text_color=theme.SIDEBAR_TEXT_MUTED).pack(anchor="w", pady=(6, 0))

        for name in [
            "Dashboard",
            "Personas",
            "Visitas",
            "Empresas",
            "Áreas",
            "Motivos",
            "Dispositivos",
            "Reconocimientos",
            "Eventos",
            "Sesiones",
        ]:
            btn = ctk.CTkButton(
                self.sidebar,
                text=name,
                width=210,
                height=40,
                corner_radius=12,
                fg_color=theme.TRANSPARENT,
                text_color=theme.SIDEBAR_TEXT,
                hover_color=theme.SIDEBAR_ACTIVE_HOVER,
                anchor="w",
                command=lambda n=name: self.show_page(n)
            )
            btn.pack(pady=4, padx=18, fill="x")
            btn.configure(font=("Arial", 15))
            self._nav_buttons[name] = btn

        ctk.CTkButton(
            self.sidebar,
            text="Cerrar sesión",
            fg_color=theme.DANGER,
            hover_color=theme.DANGER_HOVER,
            text_color=theme.PRIMARY_TEXT,
            height=40,
            corner_radius=12,
            command=self._logout
        ).pack(pady=(28, 20), padx=18, fill="x")

    def _highlight_nav(self, active: str) -> None:
        for name, btn in self._nav_buttons.items():
            if name == active:
                btn.configure(fg_color=theme.SIDEBAR_ACTIVE, text_color=theme.PRIMARY_TEXT)
            else:
                btn.configure(fg_color=theme.TRANSPARENT, text_color=theme.SIDEBAR_TEXT)

    def _logout(self):
        try:
            camera.release()
        except Exception:
            pass
        messagebox.showinfo("Sesión", "El sistema volverá a la pantalla de login")
        from .login import Login
        self.destroy()
        Login().mainloop()

    def show_page(self, name: str):
        if self.current_page is not None:
            self.current_page.destroy()
            self.current_page = None

        if name == "Dashboard":
            self.current_page = DashboardPage(self.content)
        elif name == "Empresas":
            self.current_page = EmpresasPage(self.content)
        elif name == "Áreas":
            self.current_page = AreasPage(self.content)
        elif name == "Motivos":
            self.current_page = MotivosPage(self.content)
        elif name == "Personas":
            self.current_page = PersonasPage(self.content, current_user_id=self.user_id)
        elif name == "Visitas":
            self.current_page = VisitasPage(self.content, current_user_id=self.user_id)
        elif name == "Dispositivos":
            self.current_page = DispositivosPage(self.content)
        elif name == "Reconocimientos":
            self.current_page = ReconocimientosPage(self.content, current_user_id=self.user_id)
        elif name == "Eventos":
            self.current_page = EventosPage(self.content)
        elif name == "Sesiones":
            self.current_page = SesionesPage(self.content)
        else:
            self.current_page = ctk.CTkFrame(self.content)

        self.current_page.grid(row=0, column=0, sticky="nsew")
        self._highlight_nav(name)
