import customtkinter as ctk
from ... import db

class SesionesPage(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, corner_radius=0)
        self.configure(fg_color="white")

        title = ctk.CTkLabel(self, text="Sesiones de usuario", font=("Arial", 22, "bold"))
        title.pack(anchor="w", padx=24, pady=(20, 10))

        self.table = ctk.CTkScrollableFrame(self, height=650)
        self.table.pack(fill="both", expand=True, padx=24, pady=8)

        self.refresh()

    def refresh(self):
        for w in self.table.winfo_children():
            w.destroy()
        headers = ["ID", "Usuario", "Inicio", "Fin", "Éxito", "IP"]
        for i, h in enumerate(headers):
            ctk.CTkLabel(self.table, text=h, font=("Arial", 13, "bold"), fg_color="#e9eef6", width=160).grid(row=0, column=i, padx=2, pady=2)
        for r, (sid, username, inicio, fin, exito, ip) in enumerate(db.list_sesiones(), start=1):
            values = [sid, username or "", inicio, fin, "Sí" if exito else "No", ip]
            for c, v in enumerate(values):
                ctk.CTkLabel(self.table, text=v, font=("Arial", 12), fg_color="#f5f5f5", width=160).grid(row=r, column=c, padx=2, pady=2)
