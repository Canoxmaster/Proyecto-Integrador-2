import customtkinter as ctk
from tkinter import messagebox
from ... import db

class MotivosPage(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, corner_radius=0)
        self.configure(fg_color="white")

        title = ctk.CTkLabel(self, text="Motivos de visita", font=("Arial", 22, "bold"))
        title.pack(anchor="w", padx=24, pady=(20, 10))

        form = ctk.CTkFrame(self, fg_color="#f7f7f7")
        form.pack(fill="x", padx=24, pady=8)

        self.e_nombre = ctk.CTkEntry(form, placeholder_text="Motivo", width=280)
        self.e_nombre.pack(side="left", padx=8, pady=10)
        self.e_desc = ctk.CTkEntry(form, placeholder_text="Descripción (opcional)", width=360)
        self.e_desc.pack(side="left", padx=8, pady=10)
        ctk.CTkButton(form, text="Agregar", fg_color="#6A0DAD", hover_color="#5A0CA0", command=self._add).pack(side="left", padx=8)

        self.table = ctk.CTkScrollableFrame(self, height=520)
        self.table.pack(fill="both", expand=True, padx=24, pady=8)

        self.refresh()

    def refresh(self):
        for w in self.table.winfo_children():
            w.destroy()
        headers = ["Motivo", "Descripción", "Eliminar"]
        for i, h in enumerate(headers):
            ctk.CTkLabel(self.table, text=h, font=("Arial", 13, "bold"), fg_color="#e9eef6", width=220).grid(row=0, column=i, padx=2, pady=2)
        for r, (mid, nombre, descripcion) in enumerate(db.list_motivos(), start=1):
            ctk.CTkLabel(self.table, text=nombre, font=("Arial", 12), fg_color="#f5f5f5", width=220).grid(row=r, column=0, padx=2, pady=2)
            ctk.CTkLabel(self.table, text=descripcion, font=("Arial", 12), fg_color="#f5f5f5", width=280).grid(row=r, column=1, padx=2, pady=2)
            ctk.CTkButton(self.table, text="❌", width=40, fg_color="#ff4d4d", hover_color="#e04444", command=lambda i=mid: self._delete(i)).grid(row=r, column=2, padx=2, pady=2)

    def _add(self):
        nombre = self.e_nombre.get().strip()
        descripcion = self.e_desc.get().strip() or None
        if not nombre:
            messagebox.showwarning("Validación", "Ingresa un motivo")
            return
        try:
            db.create_motivo(nombre, descripcion)
            self.e_nombre.delete(0, "end")
            self.e_desc.delete(0, "end")
            self.refresh()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _delete(self, motivo_id: int):
        if not messagebox.askyesno("Confirmar", "¿Eliminar motivo?"):
            return
        try:
            db.delete_motivo(motivo_id)
            self.refresh()
        except Exception as e:
            messagebox.showerror("Error", str(e))
