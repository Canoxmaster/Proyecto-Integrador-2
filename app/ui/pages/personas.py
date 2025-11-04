import customtkinter as ctk
from tkinter import messagebox
import cv2
import face_recognition
import numpy as np
from io import BytesIO
from PIL import Image
from .. import theme
from ... import db
from ...camera import camera

class PersonasPage(ctk.CTkFrame):
    def __init__(self, parent, current_user_id: int):
        super().__init__(parent, corner_radius=0)
        self.configure(fg_color=theme.APP_BG)
        self.current_user_id = current_user_id

        title = ctk.CTkLabel(self, text="Personas autorizadas", font=("Arial", 22, "bold"), text_color=theme.TEXT_PRIMARY)
        title.pack(anchor="w", padx=24, pady=(20, 10))

        # Formulario alta
        form = ctk.CTkFrame(self, fg_color=theme.CARD_BG, corner_radius=16, border_width=1, border_color=theme.CARD_BORDER)
        form.pack(fill="x", padx=24, pady=8)
        form.grid_columnconfigure((0, 1, 2), weight=1)

        self.e_nombre = ctk.CTkEntry(
            form,
            placeholder_text="Nombre (requerido)",
            fg_color=theme.INPUT_BG,
            text_color=theme.TEXT_PRIMARY,
        )
        self.e_nombre.grid(row=0, column=0, padx=8, pady=(12, 6), sticky="ew")

        self.e_apellido = ctk.CTkEntry(
            form,
            placeholder_text="Apellido (requerido)",
            fg_color=theme.INPUT_BG,
            text_color=theme.TEXT_PRIMARY,
        )
        self.e_apellido.grid(row=0, column=1, padx=8, pady=(12, 6), sticky="ew")

        # Combobox de empresas (solo opciones existentes)
        self.cb_empresa = ctk.CTkComboBox(
            form,
            values=[],
            state="readonly",
            button_color=theme.PRIMARY,
            border_color=theme.INPUT_BORDER,
            text_color=theme.TEXT_PRIMARY,
        )
        self.cb_empresa.set("Empresa (selecciona)")
        self.cb_empresa.grid(row=1, column=0, columnspan=3, padx=8, pady=6, sticky="ew")

        self.e_cargo = ctk.CTkEntry(
            form,
            placeholder_text="Cargo/Rol (requerido)",
            fg_color=theme.INPUT_BG,
            text_color=theme.TEXT_PRIMARY,
        )
        self.e_cargo.grid(row=0, column=2, padx=8, pady=(12, 6), sticky="ew")

        ctk.CTkButton(
            form,
            text="Guardar (con cámara)",
            fg_color=theme.PRIMARY,
            hover_color=theme.PRIMARY_HOVER,
            text_color=theme.PRIMARY_TEXT,
            command=self._add_with_capture,
        ).grid(row=2, column=0, columnspan=3, padx=16, pady=(6, 12), sticky="ew")

        # Tabla
        self.table = ctk.CTkScrollableFrame(
            self,
            height=520,
            fg_color=theme.CARD_BG,
            corner_radius=16,
            border_width=1,
            border_color=theme.CARD_BORDER,
        )
        self.table.pack(fill="both", expand=True, padx=24, pady=8)

        self._empresa_map = {}
        self._foto_thumbs = {}
        self._foto_blobs = {}
        self._load_empresas()
        self.refresh()

    def _load_empresas(self):
        try:
            empresas = db.list_empresas()
            self._empresa_map = {nombre: _id for _id, nombre, _ in empresas}
            values = list(self._empresa_map.keys())
            values.sort(key=lambda s: s.lower())
            if not values:
                values = ["(No hay empresas registradas)"]
                self.cb_empresa.configure(values=values, state="disabled")
            else:
                self.cb_empresa.configure(values=values, state="readonly")
            self.cb_empresa.set("Empresa (selecciona)")
        except Exception:
            self.cb_empresa.configure(values=["Error al cargar"], state="disabled")

    def refresh(self):
        for w in self.table.winfo_children():
            w.destroy()
        headers = ["Foto", "Nombre", "Apellido", "Empresa", "Cargo", "Eliminar"]
        for i, h in enumerate(headers):
            ctk.CTkLabel(
                self.table,
                text=h,
                font=("Arial", 13, "bold"),
                fg_color=theme.TABLE_HEADER_BG,
                text_color=theme.TABLE_HEADER_TEXT,
                width=160 if i else 120,
            ).grid(row=0, column=i, padx=4, pady=4, sticky="ew")
        self._foto_thumbs.clear()
        self._foto_blobs.clear()
        for r, (pid, tipo, nombre, apellido, empresa, cargo, activo) in enumerate(db.list_personas(tipo="AUTORIZADO"), start=1):
            bg = theme.TABLE_ROW_ALT_BG if r % 2 == 0 else theme.TABLE_ROW_BG
            self._render_foto_cell(row=r, col=0, persona_id=pid, nombre=nombre, apellido=apellido, bg=bg)
            ctk.CTkLabel(self.table, text=nombre, font=("Arial", 12), fg_color=bg, text_color=theme.TABLE_ROW_TEXT, width=140).grid(row=r, column=1, padx=4, pady=3)
            ctk.CTkLabel(self.table, text=apellido, font=("Arial", 12), fg_color=bg, text_color=theme.TABLE_ROW_TEXT, width=140).grid(row=r, column=2, padx=4, pady=3)
            ctk.CTkLabel(self.table, text=empresa, font=("Arial", 12), fg_color=bg, text_color=theme.TABLE_ROW_TEXT, width=160).grid(row=r, column=3, padx=4, pady=3)
            ctk.CTkLabel(self.table, text=cargo, font=("Arial", 12), fg_color=bg, text_color=theme.TABLE_ROW_TEXT, width=140).grid(row=r, column=4, padx=4, pady=3)
            ctk.CTkButton(self.table, text="Eliminar", width=90, fg_color=theme.DANGER, hover_color=theme.DANGER_HOVER,
                          text_color=theme.PRIMARY_TEXT, command=lambda i=pid: self._delete(i)).grid(row=r, column=5, padx=4, pady=3)

    def _render_foto_cell(self, row: int, col: int, persona_id: int, nombre: str, apellido: str, bg: str):
        blob = db.get_persona_ultima_foto(persona_id)
        if not blob:
            lbl = ctk.CTkLabel(self.table, text="Sin foto", font=("Arial", 11), fg_color=bg, text_color=theme.TABLE_MUTED_TEXT, width=110, height=80)
            lbl.grid(row=row, column=col, padx=4, pady=4)
            return
        try:
            image = Image.open(BytesIO(blob))
            thumb = ctk.CTkImage(light_image=image, dark_image=image, size=(70, 70))
            self._foto_thumbs[persona_id] = thumb
            self._foto_blobs[persona_id] = blob
            lbl = ctk.CTkLabel(self.table, image=thumb, text="", width=80, height=80, fg_color=bg)
            lbl.grid(row=row, column=col, padx=4, pady=4)
            lbl.bind("<Button-1>", lambda _e, pid=persona_id, nom=f"{nombre} {apellido}".strip(): self._mostrar_foto(pid, nom))
        except Exception:
            lbl = ctk.CTkLabel(self.table, text="Foto inválida", font=("Arial", 11), fg_color=bg, text_color=theme.DANGER, width=110, height=80)
            lbl.grid(row=row, column=col, padx=4, pady=4)

    def _mostrar_foto(self, persona_id: int, nombre: str):
        blob = self._foto_blobs.get(persona_id)
        if not blob:
            messagebox.showinfo("Foto", "No hay imagen disponible")
            return
        try:
            image = Image.open(BytesIO(blob))
        except Exception as exc:
            messagebox.showerror("Imagen", f"No fue posible abrir la imagen: {exc}")
            return
        max_size = (600, 600)
        image.thumbnail(max_size)
        img_ctk = ctk.CTkImage(light_image=image, dark_image=image, size=image.size)
        top = ctk.CTkToplevel(self)
        top.title(f"{nombre}")
        top.geometry(f"{image.size[0]+40}x{image.size[1]+40}")
        top.grab_set()
        lbl = ctk.CTkLabel(top, image=img_ctk, text="", fg_color=theme.CARD_BG)
        lbl.image = img_ctk  # evitar GC
        lbl.pack(padx=20, pady=20)
        ctk.CTkButton(
            top,
            text="Cerrar",
            command=top.destroy,
            fg_color=theme.PRIMARY,
            hover_color=theme.PRIMARY_HOVER,
            text_color=theme.PRIMARY_TEXT,
        ).pack(pady=(0, 16))

    def _delete(self, persona_id: int):
        if not messagebox.askyesno("Confirmar", "¿Eliminar persona autorizada?\nSe eliminarán sus encodings y fotos asociadas"):
            return
        try:
            db.delete_persona(persona_id)
            try:
                db.log_event("ADMIN", self.current_user_id, "BAJA_AUTORIZADO", f"PersonaID={persona_id}")
            except Exception:
                pass
            self.refresh()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _add_with_capture(self):
        nombre = self.e_nombre.get().strip()
        apellido = self.e_apellido.get().strip()
        empresa_sel = self.cb_empresa.get().strip()
        cargo = self.e_cargo.get().strip()
        if not nombre or not apellido or not cargo:
            messagebox.showwarning("Validación", "Nombre, Apellido y Cargo son requeridos")
            return
        if empresa_sel in ("", "Empresa (selecciona)", "(No hay empresas registradas)"):
            messagebox.showwarning("Validación", "Debes seleccionar una Empresa registrada desde la sección Empresas")
            return
        empresa_id = self._empresa_map.get(empresa_sel)
        if empresa_id is None:
            messagebox.showerror("Empresa", "Empresa seleccionada inválida. Actualiza la lista y vuelve a intentar.")
            return

        # Capturar rostro primero para garantizar biometría obligatoria
        if not camera.open():
            messagebox.showerror("Cámara", "No se pudo abrir la cámara")
            return
        messagebox.showinfo("Captura", "Presiona 'Espacio' para tomar la foto, 'Esc' para cancelar.")
        while True:
            ret, frame = camera.read()
            if not ret:
                break
            cv2.imshow("Captura de rostro (Autorizado)", frame)
            key = cv2.waitKey(1)
            if key % 256 == 27:
                cv2.destroyAllWindows()
                return
            elif key % 256 == 32:
                break
        cv2.destroyAllWindows()

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        encodings = face_recognition.face_encodings(rgb)
        if not encodings:
            messagebox.showwarning("Rostro", "No se detectó rostro. No se guardó la persona.")
            return
        encoding = encodings[0]
        try:
            persona_id = db.create_persona("AUTORIZADO", nombre, apellido, empresa_id, cargo)
            db.add_persona_encoding(persona_id, encoding.astype(np.float64).tobytes())
            _, buffer = cv2.imencode('.jpg', frame)
            db.add_persona_foto(persona_id, buffer.tobytes(), visita_id=None, tipo="ROSTRO")
            self.e_nombre.delete(0, "end")
            self.e_apellido.delete(0, "end")
            self.e_cargo.delete(0, "end")
            self.cb_empresa.set("Empresa (selecciona)")
            messagebox.showinfo("Guardado", "Persona autorizada y biometría guardadas")
            try:
                db.log_event("ADMIN", self.current_user_id, "ALTA_AUTORIZADO", f"PersonaID={persona_id} Nombre={nombre} {apellido}")
            except Exception:
                pass
            self.refresh()
        except Exception as e:
            messagebox.showerror("Error", str(e))
