import customtkinter as ctk
from tkinter import messagebox
import cv2
from ... import db

class DispositivosPage(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, corner_radius=0)
        self.configure(fg_color="white")

        title = ctk.CTkLabel(self, text="Dispositivos", font=("Arial", 22, "bold"))
        title.pack(anchor="w", padx=24, pady=(20, 10))

        form = ctk.CTkFrame(self, fg_color="#f7f7f7")
        form.pack(fill="x", padx=24, pady=8)

        self.e_nombre = ctk.CTkEntry(form, placeholder_text="Nombre del dispositivo", width=280)
        self.e_nombre.pack(side="left", padx=8, pady=10)
        self.e_ubicacion = ctk.CTkEntry(form, placeholder_text="Ubicación (opcional)", width=320)
        self.e_ubicacion.pack(side="left", padx=8, pady=10)
        ctk.CTkButton(form, text="Agregar", fg_color="#6A0DAD", hover_color="#5A0CA0", command=self._add).pack(side="left", padx=8)

        self.table = ctk.CTkScrollableFrame(self, height=520)
        self.table.pack(fill="both", expand=True, padx=24, pady=8)

        self.refresh()

    def refresh(self):
        for w in self.table.winfo_children():
            w.destroy()
        headers = ["Nombre", "Ubicación", "Activo", "Acciones"]
        for i, h in enumerate(headers):
            ctk.CTkLabel(self.table, text=h, font=("Arial", 13, "bold"), fg_color="#e9eef6", width=220).grid(row=0, column=i, padx=2, pady=2)
        for r, (did, nombre, ubicacion, activo) in enumerate(db.list_dispositivos(), start=1):
            ctk.CTkLabel(self.table, text=nombre, font=("Arial", 12), fg_color="#f5f5f5", width=220).grid(row=r, column=0, padx=2, pady=2)
            ctk.CTkLabel(self.table, text=ubicacion, font=("Arial", 12), fg_color="#f5f5f5", width=220).grid(row=r, column=1, padx=2, pady=2)
            ctk.CTkLabel(self.table, text=("Sí" if activo else "No"), font=("Arial", 12), fg_color="#f5f5f5", width=80).grid(row=r, column=2, padx=2, pady=2)
            actions = ctk.CTkFrame(self.table, fg_color="#f5f5f5")
            actions.grid(row=r, column=3, padx=2, pady=2)
            ctk.CTkButton(actions, text="Editar", width=80, command=lambda i=did: self._edit_dialog(i)).pack(side="left", padx=4, pady=2)
            ctk.CTkButton(actions, text="Probar", width=80, command=lambda i=did: self._test_device_by_id(i)).pack(side="left", padx=4, pady=2)
            ctk.CTkButton(actions, text="Eliminar", width=80, fg_color="#ff4d4d", hover_color="#e04444", command=lambda i=did: self._delete(i)).pack(side="left", padx=4, pady=2)

    def _add(self):
        nombre = self.e_nombre.get().strip()
        ubicacion = self.e_ubicacion.get().strip() or None
        if not nombre:
            messagebox.showwarning("Validación", "Ingresa un nombre")
            return
        db.create_dispositivo(nombre, ubicacion)
        self.e_nombre.delete(0, "end")
        self.e_ubicacion.delete(0, "end")
        self.refresh()

    def _delete(self, dispositivo_id: int):
        if not messagebox.askyesno("Confirmar", "¿Eliminar dispositivo?"):
            return
        db.delete_dispositivo(dispositivo_id)
        self.refresh()

    def _edit_dialog(self, dispositivo_id: int):
        # Buscar datos actuales
        rows = db.list_dispositivos()
        row = next((r for r in rows if r[0] == dispositivo_id), None)
        if not row:
            messagebox.showerror("Error", "Dispositivo no encontrado")
            return
        did, nombre, ubicacion, activo = row
        win = ctk.CTkToplevel(self)
        win.title(f"Editar dispositivo #{did}")
        win.geometry("520x260")
        win.grab_set()

        ctk.CTkLabel(win, text="Nombre:").pack(anchor="w", padx=16, pady=(16,4))
        e_nombre = ctk.CTkEntry(win, width=460)
        e_nombre.insert(0, nombre or "")
        e_nombre.pack(padx=16)

        ctk.CTkLabel(win, text="Ubicación (índice de cámara o URL RTSP/HTTP):").pack(anchor="w", padx=16, pady=(12,4))
        e_ubic = ctk.CTkEntry(win, width=460)
        e_ubic.insert(0, ubicacion or "")
        e_ubic.pack(padx=16)

        ctk.CTkLabel(win, text="Activo:").pack(anchor="w", padx=16, pady=(12,4))
        sw_activo = ctk.CTkSwitch(win, text="", width=40)
        sw_activo.select() if activo else sw_activo.deselect()
        sw_activo.pack(anchor="w", padx=16)

        btns = ctk.CTkFrame(win)
        btns.pack(fill="x", padx=16, pady=16)

        def on_save():
            n = e_nombre.get().strip()
            u = e_ubic.get().strip() or None
            a = bool(sw_activo.get())
            if not n:
                messagebox.showwarning("Validación", "El nombre es requerido")
                return
            db.update_dispositivo(did, n, u, a)
            win.destroy()
            self.refresh()

        def on_test():
            u = e_ubic.get().strip()
            self._test_device(u)

        ctk.CTkButton(btns, text="Guardar", fg_color="#6A0DAD", hover_color="#5A0CA0", command=on_save).pack(side="left", padx=6)
        ctk.CTkButton(btns, text="Probar", command=on_test).pack(side="left", padx=6)
        ctk.CTkButton(btns, text="Cerrar", command=win.destroy).pack(side="right", padx=6)

    def _test_device_by_id(self, dispositivo_id: int):
        rows = db.list_dispositivos()
        row = next((r for r in rows if r[0] == dispositivo_id), None)
        if not row:
            messagebox.showerror("Error", "Dispositivo no encontrado")
            return
        _, _, ubicacion, _ = row
        self._test_device(ubicacion)

    def _test_device(self, ubicacion: str | None):
        # Interpretar ubicacion como índice (entero) o URL completa
        cap = None
        try:
            if ubicacion and (ubicacion.startswith("rtsp://") or ubicacion.startswith("http://") or ubicacion.startswith("https://")):
                cap = cv2.VideoCapture(ubicacion)
            else:
                idx = None
                if ubicacion:
                    try:
                        idx = int(ubicacion)
                    except Exception:
                        pass
                if idx is None:
                    idx = 0
                # Intentar con backends comunes de Windows
                for backend in [getattr(cv2, "CAP_DSHOW", 700), getattr(cv2, "CAP_MSMF", 1400), 0]:
                    cap = cv2.VideoCapture(idx, backend) if backend != 0 else cv2.VideoCapture(idx)
                    if cap and cap.isOpened():
                        break
                    if cap:
                        cap.release()
                        cap = None
            if not cap or not cap.isOpened():
                messagebox.showerror("Cámara", "No se pudo abrir el dispositivo")
                return
            # Vista de prueba por 5 segundos o ESC
            import time
            start = time.time()
            while True:
                ok, frame = cap.read()
                if not ok:
                    break
                cv2.imshow("Prueba de dispositivo (ESC para cerrar)", frame)
                key = cv2.waitKey(1)
                if key % 256 == 27:
                    break
                if time.time() - start > 5:
                    break
            cv2.destroyAllWindows()
        finally:
            try:
                if cap:
                    cap.release()
            except Exception:
                pass
