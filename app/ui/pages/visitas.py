import customtkinter as ctk
from tkinter import messagebox
from datetime import datetime
import cv2
import numpy as np
import face_recognition
from PIL import Image
from .. import theme
from ... import db
from ...camera import camera
from ..components.motivo_dialog import MotivoDialog

class VisitasPage(ctk.CTkFrame):
    def __init__(self, parent, current_user_id: int):
        super().__init__(parent, corner_radius=0)
        self.configure(fg_color=theme.APP_BG)
        self.current_user_id = current_user_id

        title = ctk.CTkLabel(self, text="Visitas", font=("Arial", 22, "bold"), text_color=theme.TEXT_PRIMARY)
        title.pack(anchor="w", padx=24, pady=(20, 10))

        # Registro por cámara con vista previa persistente
        form = ctk.CTkFrame(self, fg_color=theme.CARD_BG, corner_radius=18, border_width=1, border_color=theme.CARD_BORDER)
        form.pack(fill="x", padx=24, pady=8)
        form.grid_columnconfigure(0, weight=1)
        form.grid_rowconfigure(0, weight=1)

        preview_wrapper = ctk.CTkFrame(form, fg_color="#0F172A", corner_radius=16)
        preview_wrapper.grid(row=0, column=0, padx=16, pady=16, sticky="nsew")
        preview_wrapper.grid_propagate(False)

        self._preview_size = (440, 320)
        self.preview_label = ctk.CTkLabel(
            preview_wrapper,
            text="Inicializando cámara...",
            width=self._preview_size[0],
            height=self._preview_size[1],
            fg_color="#111827",
            text_color=theme.PRIMARY_TEXT,
        )
        self.preview_label.pack(padx=10, pady=10)

        controls = ctk.CTkFrame(form, fg_color=theme.CARD_BG)
        controls.grid(row=0, column=1, padx=16, pady=16, sticky="n")
        controls.grid_columnconfigure(0, weight=1)

        ctk.CTkButton(
            controls,
            text="Capturar ENTRADA",
            fg_color=theme.PRIMARY,
            hover_color=theme.PRIMARY_HOVER,
            text_color=theme.PRIMARY_TEXT,
            command=self._registrar_entrada_camara,
        ).grid(row=0, column=0, sticky="ew", pady=(0, 12))
        ctk.CTkButton(
            controls,
            text="Capturar SALIDA",
            fg_color=theme.SUCCESS,
            hover_color=theme.SUCCESS_HOVER,
            text_color=theme.PRIMARY_TEXT,
            command=self._registrar_salida_camara,
        ).grid(row=1, column=0, sticky="ew", pady=(0, 12))

        self._preview_frame = preview_wrapper
        self._camera_card = form
        self._controls_frame = controls
        self._camera_layout = "side"
        self._camera_card.bind("<Configure>", self._on_camera_card_resize)

        # Tabla
        self.table = ctk.CTkScrollableFrame(
            self,
            height=520,
            fg_color=theme.CARD_BG,
            corner_radius=18,
            border_width=1,
            border_color=theme.CARD_BORDER,
        )
        self.table.pack(fill="both", expand=True, padx=24, pady=8)

        self._preview_job = None
        self._last_frame = None
        self._preview_image = None

        self.refresh()
        self._start_preview()
        self.bind("<Destroy>", self._on_destroy)

    def refresh(self):
        for w in self.table.winfo_children():
            w.destroy()
        headers = ["Nombre", "Apellido", "Empresa", "Motivo", "Área", "Entrada", "Salida", "Acciones"]
        widths = [130, 130, 150, 150, 140, 150, 150, 130]
        for i in range(len(headers)):
            self.table.grid_columnconfigure(i, weight=1)
        for i, h in enumerate(headers):
            ctk.CTkLabel(
                self.table,
                text=h,
                font=("Arial", 13, "bold"),
                fg_color=theme.TABLE_HEADER_BG,
                text_color=theme.TABLE_HEADER_TEXT,
                width=widths[i],
            ).grid(row=0, column=i, padx=4, pady=4, sticky="ew")
        for r, row in enumerate(db.list_visitas(), start=1):
            vid, nombre, apellido, empresa, motivo, area, ent, sal = row
            bg = theme.TABLE_ROW_ALT_BG if r % 2 == 0 else theme.TABLE_ROW_BG
            values = [nombre, apellido, empresa, motivo, area, ent, sal]
            for c, v in enumerate(values):
                ctk.CTkLabel(
                    self.table,
                    text=v,
                    font=("Arial", 12),
                    fg_color=bg,
                    text_color=theme.TABLE_ROW_TEXT,
                    width=widths[c],
                ).grid(row=r, column=c, padx=4, pady=3)
            if not sal:
                ctk.CTkLabel(
                    self.table,
                    text="Salida pendiente",
                    font=("Arial", 12, "italic"),
                    fg_color=bg,
                    text_color=theme.WARNING,
                    width=widths[-1],
                ).grid(row=r, column=len(headers) - 1, padx=4, pady=3)
            else:
                ctk.CTkButton(
                    self.table,
                    text="Eliminar",
                    width=widths[-1] - 20,
                    fg_color=theme.DANGER,
                    hover_color=theme.DANGER_HOVER,
                    text_color=theme.PRIMARY_TEXT,
                    command=lambda i=vid: self._delete(i),
                ).grid(row=r, column=len(headers) - 1, padx=4, pady=3)

    def _on_camera_card_resize(self, event):
        if event.widget is not self._camera_card:
            return
        width = event.width
        if width < 900 and self._camera_layout != "stacked":
            self._camera_layout = "stacked"
            self._preview_frame.grid_configure(row=0, column=0, columnspan=2, sticky="nsew", padx=16, pady=(16, 8))
            self._controls_frame.grid_configure(row=1, column=0, columnspan=2, sticky="ew", padx=16, pady=(0, 16))
            self._camera_card.grid_columnconfigure(0, weight=1)
            self._camera_card.grid_columnconfigure(1, weight=0)
        elif width >= 900 and self._camera_layout != "side":
            self._camera_layout = "side"
            self._preview_frame.grid_configure(row=0, column=0, columnspan=1, sticky="nsew", padx=16, pady=16)
            self._controls_frame.grid_configure(row=0, column=1, columnspan=1, sticky="n", padx=16, pady=16)
            self._camera_card.grid_columnconfigure(0, weight=1)
            self._camera_card.grid_columnconfigure(1, weight=0)

    def _load_autorizados_encodings(self):
        rows = db.list_autorizados_encodings()
        personas = []  # (persona_id, nombre_completo, encoding)
        for pid, nombre, apellido, empresa, blob in rows:
            try:
                arr = np.frombuffer(blob, dtype=np.float64)
                # Normalmente 128 valores
                if arr.size >= 128:
                    arr = arr[:128]
                personas.append((pid, f"{nombre} {apellido}".strip(), arr))
            except Exception:
                continue
        return personas

    def _start_preview(self):
        if self._preview_job is not None:
            return
        self._schedule_preview()

    def _schedule_preview(self):
        if not self.winfo_exists():
            return
        if not camera.open():
            self.preview_label.configure(text="Cámara no disponible", image=None)
            self._last_frame = None
        else:
            ret, frame = camera.read()
            if ret and frame is not None:
                self._last_frame = frame.copy()
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                image = Image.fromarray(rgb)
                self._preview_image = ctk.CTkImage(light_image=image, dark_image=image, size=self._preview_size)
                self.preview_label.configure(image=self._preview_image, text="")
            else:
                self.preview_label.configure(text="Sin señal", image=None)
                self._last_frame = None
        self._preview_job = self.after(60, self._schedule_preview)

    def _get_current_frame(self):
        frame = self._last_frame
        if frame is None:
            if not camera.open():
                return None
            ret, frame = camera.read()
            if not ret or frame is None:
                return None
            self._last_frame = frame.copy()
            frame = self._last_frame
        return frame.copy()

    def _on_destroy(self, event):
        if event.widget is not self:
            return
        if self._preview_job is not None:
            try:
                self.after_cancel(self._preview_job)
            except Exception:
                pass
            self._preview_job = None
        try:
            camera.release()
        except Exception:
            pass

    @staticmethod
    def _normalize_motivos(seq):
        """Devuelve lista de dicts {'id','nombre'} a partir del resultado de la base."""
        out = []
        for m in (seq or []):
            try:
                if isinstance(m, dict):
                    mid = m.get('id')
                    nombre = m.get('nombre')
                else:
                    mid, nombre = m[0], m[1]
                if mid is not None and nombre is not None:
                    out.append({"id": mid, "nombre": str(nombre)})
            except Exception:
                continue
        return out

    @staticmethod
    def _normalize_areas(seq):
        """Devuelve lista de dicts {'id','nombre'} para áreas activas."""
        out = []
        for a in (seq or []):
            try:
                aid = None
                nombre = None
                if isinstance(a, dict):
                    aid = a.get('id')
                    nombre = a.get('nombre')
                else:
                    aid = a[0]
                    nombre = a[1]
                if aid is not None and nombre is not None:
                    out.append({"id": aid, "nombre": str(nombre)})
            except Exception:
                continue
        return out

    def _registrar_entrada_camara(self):
        personas = self._load_autorizados_encodings()
        if not personas:
            messagebox.showwarning("Autorizados", "No hay personas autorizadas con biometría registrada")
            return
        frame = self._get_current_frame()
        if frame is None:
            messagebox.showwarning("Cámara", "No hay una imagen disponible para capturar. Verifica la cámara.")
            return
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        encs = face_recognition.face_encodings(rgb)
        if not encs:
            messagebox.showwarning("Rostro", "No se detectó rostro")
            return
        encoding = encs[0]
        # Comparar
        best_pid = None
        best_name = None
        best_dist = 1e9
        for pid, name, known in personas:
            try:
                d = np.linalg.norm(known - encoding)
            except Exception:
                d = face_recognition.face_distance([known], encoding)[0]
            if d < best_dist:
                best_dist = d
                best_pid = pid
                best_name = name
        THRESH = 0.6
        if best_pid is None or best_dist > THRESH:
            messagebox.showerror("No reconocido", f"No coincide con ningún autorizado (dist={best_dist:.3f})")
            return
        # Selección de motivo y área mediante diálogo (obligatorio)
        motivos = self._normalize_motivos(db.list_motivos_activos())
        areas = self._normalize_areas(db.list_areas())
        if not motivos:
            messagebox.showerror("Motivos", "No hay motivos activos. Registra al menos uno en la sección Motivos.")
            return
        if not areas:
            messagebox.showerror("Áreas", "No hay áreas activas. Registra al menos una en la sección Áreas.")
            return
        ultimo_motivo, ultimo_area = db.get_latest_visita_defaults(best_pid)
        dlg = MotivoDialog(
            self,
            motivos=motivos,
            areas=areas,
            default_motivo=ultimo_motivo,
            default_area=ultimo_area,
            on_manage_motivos=lambda: self.master.master.show_page("Motivos") if hasattr(self.master, 'master') else None,
            on_manage_areas=lambda: self.master.master.show_page("Áreas") if hasattr(self.master, 'master') else None,
        )
        selection = dlg.show_modal()
        if not selection:
            messagebox.showinfo("Cancelado", "Registro cancelado. Debes seleccionar motivo y área para continuar.")
            return
        mot_id = selection.get("motivo_id")
        area_id = selection.get("area_id")
        if not mot_id or not area_id:
            messagebox.showwarning("Incompleto", "Selecciona motivo y área válidos antes de registrar la visita.")
            return
        motivo_nombre = next((m["nombre"] for m in motivos if m["id"] == mot_id), "")
        area_nombre = next((a["nombre"] for a in areas if a["id"] == area_id), "")
        # Validar que no tenga visita abierta
        open_vid = db.get_open_visita_for_persona(best_pid)
        if open_vid:
            messagebox.showwarning("Ya abierta", f"{best_name} ya tiene una visita abierta (ID {open_vid})")
            return
        # Crear visita y evidencia
        vid = db.create_visita(best_pid, mot_id, area_id, registrado_por=self.current_user_id)
        foto_id = None
        try:
            foto_id = db.insertar_foto_visita(vid, frame, persona_id=best_pid, tipo="EVIDENCIA")
        except Exception:
            # Fallback: try to save as persona foto linked to visit
            try:
                _, buf = cv2.imencode('.jpg', frame)
                foto_id = db.add_persona_foto(best_pid, buf.tobytes(), visita_id=vid, tipo="EVIDENCIA")
            except Exception:
                foto_id = None
        if foto_id:
            try:
                db.set_visita_evidencia_principal(vid, foto_id)
            except Exception:
                pass
        messagebox.showinfo("Entrada", f"Entrada registrada para {best_name} (dist={best_dist:.3f})")
        try:
            db.log_event("ADMIN", self.current_user_id, "VISITA_ENTRADA",
                         f"VisitaID={vid} Persona={best_name} Motivo={motivo_nombre} Area={area_nombre}")
        except Exception:
            pass
        self.refresh()

    def _registrar_salida_camara(self):
        personas = self._load_autorizados_encodings()
        if not personas:
            messagebox.showwarning("Autorizados", "No hay personas autorizadas con biometría registrada")
            return
        frame = self._get_current_frame()
        if frame is None:
            messagebox.showwarning("Cámara", "No hay una imagen disponible para capturar. Verifica la cámara.")
            return
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        encs = face_recognition.face_encodings(rgb)
        if not encs:
            messagebox.showwarning("Rostro", "No se detectó rostro")
            return
        encoding = encs[0]
        best_pid = None
        best_name = None
        best_dist = 1e9
        for pid, name, known in personas:
            try:
                d = np.linalg.norm(known - encoding)
            except Exception:
                d = face_recognition.face_distance([known], encoding)[0]
            if d < best_dist:
                best_dist = d
                best_pid = pid
                best_name = name
        THRESH = 0.6
        if best_pid is None or best_dist > THRESH:
            messagebox.showerror("No reconocido", f"No coincide con ningún autorizado (dist={best_dist:.3f})")
            return
        # Buscar visita abierta y cerrarla
        vid = db.get_open_visita_for_persona(best_pid)
        if not vid:
            messagebox.showwarning("Sin visita", f"No hay visita abierta para {best_name}")
            return
        hora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db.set_visita_salida(vid, hora)
        try:
            db.log_event("ADMIN", self.current_user_id, "VISITA_SALIDA",
                         f"VisitaID={vid} Persona={best_name}")
        except Exception:
            pass
        messagebox.showinfo("Salida", f"Salida registrada para {best_name}")
        self.refresh()

    def _delete(self, visita_id: int):
        if not messagebox.askyesno("Confirmar", "¿Eliminar visita?"):
            return
        db.delete_visita(visita_id)
        try:
            db.log_event("ADMIN", self.current_user_id, "VISITA_ELIMINADA", f"VisitaID={visita_id}")
        except Exception:
            pass
        self.refresh()

