import sqlite3
import customtkinter as ctk
from tkinter import messagebox
from PIL import Image
import cv2
import face_recognition
import numpy as np
import io
import time

DB_NAME = "control_visitas.db"

def get_conn():
    conn = sqlite3.connect(DB_NAME)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def get_or_create_empresa(nombre, actividad=None):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, actividad FROM empresas WHERE nombre=?", (nombre,))
    row = cur.fetchone()
    if row:
        emp_id, act = row
        if actividad and not act:
            cur.execute("UPDATE empresas SET actividad=? WHERE id=?", (actividad, emp_id))
            conn.commit()
        conn.close()
        return emp_id
    cur.execute("INSERT INTO empresas (nombre, actividad) VALUES (?, ?)", (nombre, actividad))
    emp_id = cur.lastrowid
    conn.commit()
    conn.close()
    return emp_id

def get_or_create_area(nombre):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id FROM areas WHERE nombre=?", (nombre,))
    row = cur.fetchone()
    if row:
        conn.close()
        return row[0]
    cur.execute("INSERT INTO areas (nombre) VALUES (?)", (nombre,))
    area_id = cur.lastrowid
    conn.commit()
    conn.close()
    return area_id

def get_or_create_motivo(nombre):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id FROM motivos_visita WHERE nombre=?", (nombre,))
    row = cur.fetchone()
    if row:
        conn.close()
        return row[0]
    cur.execute("INSERT INTO motivos_visita (nombre) VALUES (?)", (nombre,))
    motivo_id = cur.lastrowid
    conn.commit()
    conn.close()
    return motivo_id

def get_or_create_persona(tipo, nombre, apellido, empresa_id=None):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id FROM personas
        WHERE tipo=? AND nombre=? AND IFNULL(apellido,'')=IFNULL(?, '') AND IFNULL(empresa_id,0)=IFNULL(?,0)
        """,
        (tipo, nombre, apellido, empresa_id)
    )
    row = cur.fetchone()
    if row:
        conn.close()
        return row[0]
    cur.execute(
        "INSERT INTO personas (tipo, nombre, apellido, empresa_id) VALUES (?,?,?,?)",
        (tipo, nombre, apellido, empresa_id)
    )
    persona_id = cur.lastrowid
    conn.commit()
    conn.close()
    return persona_id

class RegistroFacial:
    def __init__(self, parent):
        self.parent = parent
        self.entry_autorizado = {}
        self.entry_fields = {}
        self.foto_cv2 = None
        self.encoding_actual = None
        self.photo_preview_autorizado = None

        self.mostrar_formulario_registro()

    # Gestor de cámara persistente en este módulo para abrir más rápido
    class CameraManager:
        def __init__(self):
            self.cap = None

        def open(self):
            if self.cap is not None and self.cap.isOpened():
                return True
            preferred_backends = [
                getattr(cv2, "CAP_DSHOW", 700),
                getattr(cv2, "CAP_MSMF", 1400),
                0,
            ]
            for backend in preferred_backends:
                cap = None
                try:
                    cap = cv2.VideoCapture(0, backend) if backend != 0 else cv2.VideoCapture(0)
                    if not cap or not cap.isOpened():
                        if cap:
                            cap.release()
                        continue
                    try:
                        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                        cap.set(cv2.CAP_PROP_FPS, 30)
                        if hasattr(cv2, "CAP_PROP_BUFFERSIZE"):
                            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                    except Exception:
                        pass
                    # pequeño warm-up
                    start = time.time()
                    while time.time() - start < 0.25:
                        cap.grab()
                    self.cap = cap
                    return True
                except Exception:
                    try:
                        if cap:
                            cap.release()
                    except Exception:
                        pass
                    continue
            return False

        def read(self):
            if self.cap is None or not self.cap.isOpened():
                if not self.open():
                    return False, None
            try:
                self.cap.grab()
            except Exception:
                pass
            return self.cap.read()

        def release(self):
            if self.cap is not None:
                try:
                    self.cap.release()
                except Exception:
                    pass
                self.cap = None

    camera = CameraManager()

    def capturar_y_comparar_foto(self):
        if not self.camera.open():
            messagebox.showerror("Error", "No se pudo abrir la cámara.")
            return

        messagebox.showinfo("Instrucciones", "Presiona 'Espacio' para tomar la foto, 'Esc' para cancelar.")

        while True:
            ret, frame = self.camera.read()
            if not ret:
                break

            cv2.imshow("Captura de rostro", frame)
            key = cv2.waitKey(1)

            if key % 256 == 27:
                cv2.destroyAllWindows()
                return
            elif key % 256 == 32:
                break
        cv2.destroyAllWindows()

        img_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img_pil = Image.fromarray(img_rgb).resize((207, 169))
        self.photo_preview_autorizado = ctk.CTkImage(img_pil, size=(207, 169))
        self.lbl_foto_autorizado.configure(image=self.photo_preview_autorizado, text="")
        self.foto_cv2 = frame

        faces = face_recognition.face_encodings(img_rgb)
        if not faces:
            messagebox.showerror("Error", "No se detectó ningún rostro.")
            return

        self.encoding_actual = faces[0]

        conn = get_conn()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT p.nombre, p.apellido, IFNULL(e.nombre,''), fe.encoding_vector
            FROM personas p
            LEFT JOIN empresas e ON e.id = p.empresa_id
            JOIN facial_encodings fe ON fe.persona_id = p.id
            WHERE p.tipo='AUTORIZADO' AND fe.encoding_vector IS NOT NULL
            """
        )
        candidatos = cursor.fetchall()
        conn.close()

        for nombre, apellido, empresa, enc_blob in candidatos:
            enc_guardado = np.frombuffer(enc_blob, dtype=np.float64)
            distancia = face_recognition.face_distance([enc_guardado], self.encoding_actual)[0]
            if distancia < 0.5:
                if messagebox.askyesno("Coincidencia encontrada", f"¿Deseas usar los datos de {nombre} {apellido} de {empresa}?"):
                    for campo, valor in {
                        "Nombre": nombre,
                        "Apellido": apellido,
                        "Empresa": empresa
                    }.items():
                        entry = self.entry_fields.get(campo)
                        if entry:
                            entry.delete(0, "end")
                            entry.insert(0, valor)
                break

    def mostrar_formulario_registro(self):
        for widget in self.parent.winfo_children():
            widget.destroy()

        title = ctk.CTkLabel(self.parent, text="Nuevo Registro", font=("Arial", 22, "bold"))
        title.pack(anchor="nw", padx=30, pady=(20, 10))

        form_frame = ctk.CTkFrame(self.parent, fg_color="white")
        form_frame.pack(pady=10)

        campos_izquierda = ["Nombre", "Empresa", "Motivo"]
        campos_derecha = ["Apellido", "Área", "Entrada"]

        for i, campo in enumerate(campos_izquierda):
            lbl = ctk.CTkLabel(form_frame, text=campo, font=("Arial", 14), anchor="w")
            lbl.grid(row=i, column=0, sticky="w", padx=10, pady=5)
            entry = ctk.CTkEntry(form_frame, width=300)
            entry.grid(row=i, column=1, padx=10, pady=5)
            self.entry_fields[campo] = entry

        for i, campo in enumerate(campos_derecha):
            lbl = ctk.CTkLabel(form_frame, text=campo, font=("Arial", 14), anchor="w")
            lbl.grid(row=i, column=2, sticky="w", padx=10, pady=5)
            entry = ctk.CTkEntry(form_frame, width=300)
            if campo == "Entrada":
                from datetime import datetime
                entry.insert(0, datetime.now().strftime("%I:%M %p"))
                entry.configure(state="disabled")
            entry.grid(row=i, column=3, padx=10, pady=5)
            self.entry_fields[campo] = entry

        self.lbl_foto_autorizado = ctk.CTkLabel(
            self.parent,
            text="Haz clic para tomar foto",
            font=("Arial", 12),
            width=207,
            height=169,
            fg_color="#dddddd",
            corner_radius=10
        )
        self.lbl_foto_autorizado.pack(pady=(10, 5))
        self.lbl_foto_autorizado.bind("<Button-1>", lambda e: self.capturar_y_comparar_foto())

        btn_guardar = ctk.CTkButton(
            self.parent, text="Guardar", fg_color="#4CAF50", hover_color="#45a049",
            text_color="white", width=140, corner_radius=10,
            command=self.guardar_registro
        )
        btn_guardar.pack(pady=20)

    def guardar_registro(self):
        datos = [self.entry_fields[campo].get() for campo in ["Nombre", "Apellido", "Empresa", "Motivo", "Área", "Entrada"]]

        if any(dato.strip() == "" for dato in datos):
            messagebox.showwarning("Campos vacíos", "Por favor completa todos los campos.")
            return

        if not hasattr(self, "foto_cv2") or not hasattr(self, "encoding_actual"):
            messagebox.showwarning("Faltan datos", "Toma una foto antes de guardar.")
            return

        nombre, apellido, empresa_nombre, motivo_nombre, area_nombre, _entrada = datos

        empresa_id = get_or_create_empresa(empresa_nombre)
        motivo_id = get_or_create_motivo(motivo_nombre)
        area_id = get_or_create_area(area_nombre)
        persona_id = get_or_create_persona("VISITANTE", nombre, apellido, empresa_id)

        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO visitas (persona_id, motivo_id, area_id) VALUES (?,?,?)",
            (persona_id, motivo_id, area_id)
        )
        visita_id = cur.lastrowid
        # Foto evidencia
        _, buffer = cv2.imencode('.jpg', self.foto_cv2)
        foto_blob = buffer.tobytes()
        conn.commit()
        conn.close()

        # Insertar foto vinculada a la visita
        conn2 = get_conn()
        cur2 = conn2.cursor()
        cur2.execute(
            "INSERT INTO fotos (persona_id, visita_id, imagen_blob, tipo) VALUES (?,?,?,?)",
            (persona_id, visita_id, foto_blob, "EVIDENCIA")
        )
        foto_id = cur2.lastrowid
        cur2.execute("UPDATE visitas SET evidencia_principal_foto_id=? WHERE id=?", (foto_id, visita_id))
        conn2.commit()
        conn2.close()

        messagebox.showinfo("Éxito", "Registro guardado exitosamente.")