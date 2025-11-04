import customtkinter as ctk


class MotivoDialog(ctk.CTkToplevel):
    def __init__(self, master, *, motivos, areas, default_motivo=None, default_area=None,
                 on_manage_motivos=None, on_manage_areas=None):
        super().__init__(master)
        self.title("Selecciona el motivo de la visita")
        self.geometry("480x360")
        self.resizable(False, False)
        self.grab_set()
        self.focus()

        self._motivos = motivos or []
        self._areas = areas or []
        self._default_motivo = default_motivo
        self._default_area = default_area
        self._on_manage = on_manage_motivos
        self._on_manage_area = on_manage_areas
        self.result = None

        # Layout
        pad = {"padx": 14, "pady": 10}
        title = ctk.CTkLabel(self, text="Motivo y área de la visita", font=ctk.CTkFont(size=18, weight="bold"))
        title.pack(**pad)

        # Combo de motivos
        motivo_names = [m["nombre"] for m in self._motivos]
        self._motivo_by_name = {m["nombre"]: m["id"] for m in self._motivos}
        self._motivo_by_id = {m["id"]: m["nombre"] for m in self._motivos}
        combo_frame = ctk.CTkFrame(self)
        combo_frame.pack(fill="x", **pad)
        ctk.CTkLabel(combo_frame, text="Motivo (obligatorio):").pack(anchor="w", padx=10, pady=(8, 6))
        self.combo_motivo = ctk.CTkComboBox(combo_frame, values=motivo_names, width=360, state="readonly" if motivo_names else "disabled")
        self.combo_motivo.pack(padx=10, pady=(0, 10))
        default_m_name = self._motivo_by_id.get(self._default_motivo) if self._default_motivo else None
        if default_m_name and default_m_name in motivo_names:
            self.combo_motivo.set(default_m_name)
        elif motivo_names:
            self.combo_motivo.set(motivo_names[0])
        else:
            self.combo_motivo.set("No hay motivos disponibles")

        if not motivo_names and self._on_manage:
            ctk.CTkButton(self, text="Abrir Motivos", command=self._on_manage).pack(**pad)

        # Combo de áreas
        area_names = [a["nombre"] for a in self._areas]
        self._area_by_name = {a["nombre"]: a["id"] for a in self._areas}
        self._area_by_id = {a["id"]: a["nombre"] for a in self._areas}
        area_frame = ctk.CTkFrame(self)
        area_frame.pack(fill="x", **pad)
        ctk.CTkLabel(area_frame, text="Área a visitar (obligatorio):").pack(anchor="w", padx=10, pady=(8, 6))
        self.combo_area = ctk.CTkComboBox(area_frame, values=area_names, width=360, state="readonly" if area_names else "disabled")
        self.combo_area.pack(padx=10, pady=(0, 10))
        default_a_name = self._area_by_id.get(self._default_area) if self._default_area else None
        if default_a_name and default_a_name in area_names:
            self.combo_area.set(default_a_name)
        elif area_names:
            self.combo_area.set(area_names[0])
        else:
            self.combo_area.set("No hay áreas disponibles")

        if not area_names and self._on_manage_area:
            ctk.CTkButton(self, text="Abrir Áreas", command=self._on_manage_area).pack(**pad)

        # Botones acción
        actions = ctk.CTkFrame(self)
        actions.pack(fill="x", **pad)
        self.btn_cancel = ctk.CTkButton(actions, text="Cancelar", fg_color="#444", command=self._cancel)
        self.btn_cancel.pack(side="left", padx=8)
        self.btn_ok = ctk.CTkButton(actions, text="Confirmar", command=self._confirm)
        self.btn_ok.pack(side="right", padx=8)

        # Atajos
        self.bind("<Escape>", lambda e: self._cancel())
        self.bind("<Return>", lambda e: self._confirm())

        # Si faltan catálogos, deshabilitar confirmar
        if not motivo_names or not area_names:
            self.btn_ok.configure(state="disabled")

    def _confirm(self):
        motivo_name = self.combo_motivo.get().strip() if self.combo_motivo else ""
        area_name = self.combo_area.get().strip() if self.combo_area else ""
        if motivo_name in self._motivo_by_name and area_name in self._area_by_name:
            self.result = {
                "motivo_id": self._motivo_by_name[motivo_name],
                "area_id": self._area_by_name[area_name],
            }
            self.destroy()

    def _cancel(self):
        self.result = None
        self.destroy()

    def show_modal(self):
        self.wait_window(self)
        return self.result