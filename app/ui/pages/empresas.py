import customtkinter as ctk
from tkinter import messagebox
from ... import db

class EmpresasPage(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, corner_radius=0)
        self.configure(fg_color="white")

        title = ctk.CTkLabel(self, text="Empresas", font=("Arial", 22, "bold"))
        title.pack(anchor="w", padx=24, pady=(20, 10))

        form = ctk.CTkFrame(self, fg_color="#f7f7f7")
        form.pack(fill="x", padx=24, pady=8)

        self.e_nombre = ctk.CTkEntry(form, placeholder_text="Nombre de la empresa", width=300)
        self.e_nombre.pack(side="left", padx=8, pady=10)
        self.e_actividad = ctk.CTkEntry(form, placeholder_text="Actividad (opcional)", width=300)
        self.e_actividad.pack(side="left", padx=8, pady=10)
        ctk.CTkButton(form, text="Agregar", fg_color="#6A0DAD", hover_color="#5A0CA0", command=self._add).pack(side="left", padx=8)

        self.table = ctk.CTkScrollableFrame(self, height=520)
        self.table.pack(fill="both", expand=True, padx=24, pady=8)

        self.refresh()

    def refresh(self):
        for w in self.table.winfo_children():
            w.destroy()
        headers = ["Nombre", "Actividad", "Eliminar"]
        for i, h in enumerate(headers):
            ctk.CTkLabel(self.table, text=h, font=("Arial", 13, "bold"), fg_color="#e9eef6", width=200).grid(row=0, column=i, padx=2, pady=2)
        for r, (eid, nombre, actividad) in enumerate(db.list_empresas(), start=1):
            ctk.CTkLabel(self.table, text=nombre, font=("Arial", 12), fg_color="#f5f5f5", width=200).grid(row=r, column=0, padx=2, pady=2)
            ctk.CTkLabel(self.table, text=actividad, font=("Arial", 12), fg_color="#f5f5f5", width=200).grid(row=r, column=1, padx=2, pady=2)
            ctk.CTkButton(self.table, text="❌", width=40, fg_color="#ff4d4d", hover_color="#e04444", command=lambda i=eid: self._delete(i)).grid(row=r, column=2, padx=2, pady=2)

    def _add(self):
        nombre = self.e_nombre.get().strip()
        actividad = self.e_actividad.get().strip() or None
        if not nombre:
            messagebox.showwarning("Validación", "Ingresa un nombre")
            return
        try:
            db.create_empresa(nombre, actividad)
            self.e_nombre.delete(0, "end")
            self.e_actividad.delete(0, "end")
            self.refresh()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _delete(self, emp_id: int):
        if not messagebox.askyesno("Confirmar", "¿Eliminar empresa?\n(Se mantendrán personas existentes, pero sin empresa)"):
            return
        try:
            db.delete_empresa(emp_id)
            self.refresh()
        except Exception as e:
            messagebox.showerror("Error", str(e))
