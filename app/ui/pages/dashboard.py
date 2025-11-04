import customtkinter as ctk
from ... import db

class DashboardPage(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, corner_radius=0)
        self.configure(fg_color="white")

        title = ctk.CTkLabel(self, text="Dashboard", font=("Arial", 22, "bold"))
        title.pack(anchor="w", padx=24, pady=(20, 10))

        # Simple KPIs
        kpi = ctk.CTkFrame(self, fg_color="#f7f7f7")
        kpi.pack(fill="x", padx=24, pady=10)
        for text, count in self._kpis():
            lbl = ctk.CTkLabel(kpi, text=f"{text}: {count}", font=("Arial", 16))
            lbl.pack(side="left", padx=18, pady=12)

        # Últimas visitas
        frame = ctk.CTkFrame(self, fg_color="#f7f7f7")
        frame.pack(fill="both", expand=True, padx=24, pady=10)
        ctk.CTkLabel(frame, text="Últimas visitas", font=("Arial", 16, "bold")).pack(anchor="w", padx=12, pady=8)

        table = ctk.CTkScrollableFrame(frame, height=400)
        table.pack(fill="both", expand=True, padx=12, pady=(0,12))

        headers = ["Nombre", "Apellido", "Empresa", "Motivo", "Área", "Entrada", "Salida"]
        for i, h in enumerate(headers):
            ctk.CTkLabel(table, text=h, font=("Arial", 13, "bold"), fg_color="#e9eef6", width=140).grid(row=0, column=i, padx=2, pady=2)

        for r, row in enumerate(db.list_visitas(limit=12), start=1):
            _, nombre, apellido, empresa, motivo, area, ent, sal = row
            values = [nombre, apellido, empresa, motivo, area, ent, sal]
            for c, v in enumerate(values):
                ctk.CTkLabel(table, text=v, font=("Arial", 12), fg_color="#f5f5f5", width=140).grid(row=r, column=c, padx=2, pady=2)

    def _kpis(self):
        # Conteos simples
        try:
            personas = len(db.list_personas())
            visitas = len(db.list_visitas(limit=999999))
            empresas = len(db.list_empresas())
            dispositivos = len(db.list_dispositivos())
        except Exception:
            personas = visitas = empresas = dispositivos = 0
        return [
            ("Personas", personas),
            ("Visitas", visitas),
            ("Empresas", empresas),
            ("Dispositivos", dispositivos),
        ]
