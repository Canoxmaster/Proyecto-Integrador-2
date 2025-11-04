import sqlite3
import customtkinter as ctk
from PIL import Image
import os
from datetime import datetime
from tkinter import messagebox
from tkinter import filedialog
import face_recognition
import numpy as np
import cv2
import io
import time
import threading

# Nueva base de datos del sistema
DB_NAME = "control_visitas.db"

def get_conn():
    conn = sqlite3.connect(DB_NAME)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def ensure_db_exists():
    """Si la base de datos no existe, crea el esquema usando Codigo_db.main()."""
    try:
        if not os.path.exists(os.path.join(os.path.dirname(__file__), DB_NAME)) and not os.path.exists(DB_NAME):
            # Intentar crear ejecutando el generador de esquema
            try:
                import Codigo_db
                Codigo_db.main()
            except Exception:
                pass
    except Exception:
        # No bloquear la app por errores de chequeo de archivo
        pass

def ensure_default_admin():
    """Crea un usuario admin por defecto si no existe."""
    conn = get_conn()
    cur = conn.cursor()
    try:
        # Verificar existencia de tabla usuarios_admin (por si la DB no está inicializada)
        cur.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='usuarios_admin'
        """)
        if cur.fetchone() is None:
            conn.close()
            return
        cur.execute("SELECT COUNT(*) FROM usuarios_admin WHERE username=?", ("admin",))
        if cur.fetchone()[0] == 0:
            cur.execute(
                "INSERT INTO usuarios_admin (username, password_hash, nombre, rol, activo) VALUES (?,?,?,?,1)",
                ("admin", "1234", "Administrador", "ADMIN")
            )
            conn.commit()
    finally:
        conn.close()

def get_or_create_empresa(nombre, actividad=None):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, actividad FROM empresas WHERE nombre=?", (nombre,))
    row = cur.fetchone()
    if row:
        emp_id, act = row
        # Si se proporciona actividad y está vacía en DB, actualizamos
        if actividad and (not act):
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

def get_or_create_persona(tipo, nombre, apellido, empresa_id=None, cargo_rol=None):
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
        "INSERT INTO personas (tipo, nombre, apellido, empresa_id, cargo_rol) VALUES (?,?,?,?,?)",
        (tipo, nombre, apellido, empresa_id, cargo_rol)
    )
    persona_id = cur.lastrowid
    conn.commit()
    conn.close()
    return persona_id

def insertar_foto(persona_id=None, visita_id=None, imagen_blob=None, tipo="ROSTRO"):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO fotos (persona_id, visita_id, imagen_blob, tipo) VALUES (?,?,?,?)",
        (persona_id, visita_id, imagen_blob, tipo)
    )
    foto_id = cur.lastrowid
    conn.commit()
    conn.close()
    return foto_id

def insertar_encoding(persona_id, encoding_vector: np.ndarray):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO facial_encodings (persona_id, encoding_vector) VALUES (?, ?)",
        (persona_id, encoding_vector.astype(np.float64).tobytes())
    )
    conn.commit()
    conn.close()
    
def bytes_to_encoding(blob: bytes) -> np.ndarray:
    if blob is None:
        return None
    try:
        return np.frombuffer(blob, dtype=np.float64)
    except Exception:
        return None


# Gestor de cámara persistente para abrirla más rápido
class CameraManager:
    def __init__(self):
        self.cap = None

    def open(self):
        # Si ya está abierta, no volver a abrir
        if self.cap is not None and self.cap.isOpened():
            return True
        # Intentar con backends más rápidos en Windows
        preferred_backends = [
            getattr(cv2, "CAP_DSHOW", 700),  # DirectShow
            getattr(cv2, "CAP_MSMF", 1400),  # Media Foundation
            0,  # por defecto
        ]
        for backend in preferred_backends:
            cap = None
            try:
                cap = cv2.VideoCapture(0, backend) if backend != 0 else cv2.VideoCapture(0)
                if not cap or not cap.isOpened():
                    if cap:
                        cap.release()
                    continue
                # Sugerir propiedades para reducir latencia
                try:
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                    cap.set(cv2.CAP_PROP_FPS, 30)
                    if hasattr(cv2, "CAP_PROP_BUFFERSIZE"):
                        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                except Exception:
                    pass

                # Pequeño warm-up para estabilizar exposición (no bloquear mucho)
                start = time.time()
                while time.time() - start < 0.25:  # ~250ms
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
        # Vaciar 1-2 frames para evitar latencia de buffer
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

# Instancia global compartida
camera = CameraManager()


# Helper para cargar imágenes en CTk con fallback si el archivo no existe
def load_ctk_image(path, size, fallback_color=(220, 220, 220)):
    """Intenta cargar una imagen desde `path` y devuelve un ctk.CTkImage.
    Si la carga falla (archivo no encontrado u otro error), crea una imagen RGBA
    sólida del tamaño indicado y color `fallback_color`.
    """
    # Si la ruta no es absoluta, resolverla relativa al directorio del script
    if not os.path.isabs(path):
        base_dir = os.path.dirname(__file__)
        path = os.path.join(base_dir, path)

    try:
        img = Image.open(path).convert("RGBA")
    except Exception:
        # Crear una imagen de reemplazo del tamaño solicitado
        img = Image.new("RGBA", size, fallback_color)
    return ctk.CTkImage(img, size=size)

class MenuPrincipal(ctk.CTk):
    def capturar_y_comparar_foto(self):
        # Usar cámara persistente para abrir más rápido
        if not camera.open():
            messagebox.showerror("Error", "No se pudo abrir la cámara.")
            return

        messagebox.showinfo("Instrucciones", "Presiona 'Espacio' para tomar la foto, 'Esc' para cancelar.")

        while True:
            ret, frame = camera.read()
            if not ret:
                break

            cv2.imshow("Captura de rostro", frame)
            key = cv2.waitKey(1)

            if key % 256 == 27:  # Esc
                cv2.destroyAllWindows()
                return
            elif key % 256 == 32:  # Space
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
            SELECT p.nombre, p.apellido, IFNULL(e.nombre,'') as empresa, fe.encoding_vector
            FROM personas p
            LEFT JOIN empresas e ON e.id = p.empresa_id
            JOIN facial_encodings fe ON fe.persona_id = p.id
            WHERE p.tipo = 'AUTORIZADO' AND fe.encoding_vector IS NOT NULL
            """
        )
        encontrados = cursor.fetchall()
        conn.close()

        for nombre, apellido, empresa, blob in encontrados:
            encoding_guardado = bytes_to_encoding(blob)
            if encoding_guardado is None:
                continue
            distancia = face_recognition.face_distance([encoding_guardado], self.encoding_actual)[0]
            if distancia < 0.5:
                respuesta = messagebox.askyesno("Coincidencia encontrada",
                                                f"¿Deseas usar los datos de {nombre} {apellido} de {empresa}?")
                if respuesta:
                    # Detectar qué conjunto de campos está activo
                    entries = getattr(self, "entry_fields", None)
                    if entries is None:
                        entries = getattr(self, "entry_autorizado", {})

                    for campo, valor in {
                        "Nombre": nombre,
                        "Apellido": apellido,
                        "Empresa": empresa
                    }.items():
                        if campo in entries:
                            entries[campo].delete(0, "end")
                            entries[campo].insert(0, valor)
                break

    def __init__(self):
        super().__init__()
        self.title("Menú")
        self.geometry("1300x700")  # Ventana más ancha
        self.resizable(False, False)
        self.configure(fg_color="white")

        # Asegurar que exista un usuario admin para iniciar sesión
        ensure_default_admin()

        # Calentar cámara en background para reducir la latencia de apertura
        try:
            threading.Thread(target=camera.open, daemon=True).start()
        except Exception:
            pass

        self.sidebar_visible = True
        # Íconos (usar helper para evitar FileNotFoundError si faltan las imágenes)
        self.hamburger_icon = load_ctk_image("menu_icon.png", (25, 25))
        self.user_icon = load_ctk_image("user_icon_lavanda_rounded.png", (100, 100))

        # Layout principal
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Sidebar
        self.sidebar = ctk.CTkFrame(self, width=250, fg_color="#d9d9d9", corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="ns")

        # Contenido
        self.content = ctk.CTkFrame(self, fg_color="white")
        self.content.grid(row=0, column=1, sticky="nsew")

        # Botón toggle
        self.btn_toggle_sidebar = ctk.CTkButton(
            self.sidebar, image=self.hamburger_icon, text="", width=30, height=30,
            fg_color="transparent", hover_color="#d0d0d0", command=self.toggle_sidebar
        )
        self.btn_toggle_sidebar.pack(anchor="ne", pady=10, padx=10)

        avatar_label = ctk.CTkLabel(self.sidebar, image=self.user_icon, text="", fg_color="transparent")
        avatar_label.pack(pady=(10, 5))

        user_label = ctk.CTkLabel(self.sidebar, text="Usuario", font=("Arial", 16, "bold"), text_color="black")
        user_label.pack(pady=(0, 20))

        # Botones menú

        self.btn_usuarios = ctk.CTkButton(
            self.sidebar, text="Usuarios", fg_color="white", text_color="black",
            hover_color="#e6e6e6", command=self.mostrar_gestion_usuarios
        )
        self.btn_usuarios.pack(pady=5, fill="x", padx=15)




        # Botón hamburguesa flotante
        self.btn_floating = ctk.CTkButton(
            self, image=self.hamburger_icon, text="", width=30, height=30,
            fg_color="transparent", hover_color="#eeeeee", command=self.toggle_sidebar
        )
        self.btn_floating.place(x=10, y=10)
        self.btn_floating.lower()

        self.btn_lista = ctk.CTkButton(self.sidebar, text="Lista de registro", fg_color="white", text_color="black",
                                       hover_color="#e6e6e6", command=self.mostrar_lista_registro)
        self.btn_lista.pack(pady=5, fill="x", padx=15)

        self.btn_bd = ctk.CTkButton(self.sidebar, text="Base de Datos", fg_color="white", text_color="black",
                                    hover_color="#e6e6e6", command=self.mostrar_base_datos)
        self.btn_bd.pack(pady=5, fill="x", padx=15)

        # Simulador de registros
        self.registros = []


    def toggle_sidebar(self):
        if self.sidebar_visible:
            self.sidebar.grid_remove()
            self.btn_floating.lift()
            self.sidebar_visible = False
        else:
            self.sidebar.grid(row=0, column=0, sticky="ns")
            self.btn_floating.lower()
            self.sidebar_visible = True

    def eliminar_fila(self, row):
        # Eliminar la fila seleccionada
        del self.registros[row]
        messagebox.showinfo("Eliminado", "El registro ha sido eliminado.")
        self.mostrar_lista_registro()

    def mostrar_gestion_usuarios(self):
        for widget in self.content.winfo_children():
            widget.destroy()

        title = ctk.CTkLabel(self.content, text="Gestión de Usuarios", font=("Arial", 22, "bold"))
        title.pack(anchor="nw", padx=30, pady=(20, 10))

        # Formulario para agregar nuevo usuario
        form_frame = ctk.CTkFrame(self.content, fg_color="white")
        form_frame.pack(pady=10)

        lbl_user = ctk.CTkLabel(form_frame, text="Usuario:", font=("Arial", 14))
        lbl_user.grid(row=0, column=0, padx=10, pady=5)
        entry_user = ctk.CTkEntry(form_frame, width=200)
        entry_user.grid(row=0, column=1, padx=10, pady=5)

        lbl_pass = ctk.CTkLabel(form_frame, text="Contraseña:", font=("Arial", 14))
        lbl_pass.grid(row=1, column=0, padx=10, pady=5)
        entry_pass = ctk.CTkEntry(form_frame, width=200)
        entry_pass.grid(row=1, column=1, padx=10, pady=5)

        def agregar_usuario():
            usuario = entry_user.get()
            contrasena = entry_pass.get()

            if usuario.strip() == "" or contrasena.strip() == "":
                messagebox.showwarning("Error", "Debes completar todos los campos.")
                return

            conn = get_conn()
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "INSERT INTO usuarios_admin (username, password_hash, nombre, rol, activo) VALUES (?,?,?,?,1)",
                    (usuario, contrasena, usuario, "ADMIN")
                )
            except sqlite3.IntegrityError:
                conn.close()
                messagebox.showerror("Error", "El usuario ya existe.")
                return
            conn.commit()
            conn.close()

            messagebox.showinfo("Usuario agregado", f"El usuario '{usuario}' fue agregado exitosamente.")
            self.mostrar_gestion_usuarios()

        btn_agregar = ctk.CTkButton(form_frame, text="Agregar Usuario", fg_color="#6A0DAD", text_color="white",
                                    hover_color="#5A0CA0", corner_radius=8, command=agregar_usuario)
        btn_agregar.grid(row=2, columnspan=2, pady=10)

        # Tabla de usuarios existentes
        tabla = ctk.CTkScrollableFrame(self.content, height=400, fg_color="#f5f5f5", corner_radius=10)
        tabla.pack(fill="both", expand=True, padx=30, pady=10)

        encabezados = ["Usuario", "Eliminar"]
        for i, texto in enumerate(encabezados):
            etiqueta = ctk.CTkLabel(tabla, text=texto, font=("Arial", 13, "bold"), text_color="black",
                                    fg_color="#cde4f9", width=150 if i == 0 else 50, anchor="center")
            etiqueta.grid(row=0, column=i, padx=1, pady=1)
        conn = get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT id, username FROM usuarios_admin WHERE activo=1")
        usuarios = cursor.fetchall()
        conn.close()

        for r, (id_usuario, usuario) in enumerate(usuarios, start=1):
            label_user = ctk.CTkLabel(tabla, text=usuario, font=("Arial", 12), text_color="black",
                                      width=150, fg_color="#eeeeee")
            label_user.grid(row=r, column=0, padx=1, pady=1)

            def eliminar_usuario(id_usuario=id_usuario):
                confirm = messagebox.askyesno("Confirmar", "¿Seguro que quieres eliminar este usuario?")
                if confirm:
                    conn = get_conn()
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM usuarios_admin WHERE id=?", (id_usuario,))
                    conn.commit()
                    conn.close()
                    messagebox.showinfo("Eliminado", "Usuario eliminado exitosamente.")
                    self.mostrar_gestion_usuarios()

            btn_eliminar = ctk.CTkButton(tabla, text="❌", width=40, height=30, font=("Arial", 14),
                                         fg_color="#ff4d4d", hover_color="#ff1a1a", text_color="white",
                                         corner_radius=5, command=eliminar_usuario)
            btn_eliminar.grid(row=r, column=1, padx=1, pady=1)

    def mostrar_formulario_registro(self):
        for widget in self.content.winfo_children():
            widget.destroy()

        # Título
        title = ctk.CTkLabel(self.content, text="Nuevo Registro", font=("Arial", 24, "bold"))
        title.pack(anchor="nw", padx=30, pady=(20, 10))

        # Botón Regresar
        btn_regresar = ctk.CTkButton(
            self.content, text="Regresar", fg_color="#6A0DAD", text_color="white",
            hover_color="#5A0CA0", corner_radius=8, width=140,
            command=self.mostrar_lista_registro
        )
        btn_regresar.place(relx=1.0, x=-30, y=30, anchor="ne")

        # Frame con dos columnas
        form_frame = ctk.CTkFrame(self.content, fg_color="transparent")
        form_frame.pack(padx=40, pady=20)

        campos_izquierda = ["Nombre", "Empresa", "Motivo"]
        campos_derecha = ["Apellido", "Área", "Entrada"]
        self.entry_fields = {}

        for i, campo in enumerate(campos_izquierda):
            lbl = ctk.CTkLabel(form_frame, text=campo, font=("Arial", 14), anchor="w")
            lbl.grid(row=i, column=0, sticky="w", padx=10, pady=10)
            entry = ctk.CTkEntry(form_frame, width=300, height=40, corner_radius=10)
            entry.grid(row=i, column=1, padx=10, pady=10)
            self.entry_fields[campo] = entry

        for i, campo in enumerate(campos_derecha):
            lbl = ctk.CTkLabel(form_frame, text=campo, font=("Arial", 14), anchor="w")
            lbl.grid(row=i, column=2, sticky="w", padx=10, pady=10)
            if campo == "Entrada":
                # Mostrar la hora actual automáticamente
                hora_actual = datetime.now().strftime("%I:%M %p")
                entry = ctk.CTkEntry(form_frame, width=300, height=40, corner_radius=10)
                entry.insert(0, hora_actual)
                entry.configure(state="disabled")  # Deshabilitar edición
            else:
                entry = ctk.CTkEntry(form_frame, width=300, height=40, corner_radius=10)
            entry.grid(row=i, column=3, padx=10, pady=10)
            self.entry_fields[campo] = entry

        # Opción para cargar foto
        self.lbl_foto_autorizado = ctk.CTkLabel(
            self.content, text="Haz clic para tomar foto",
            font=("Arial", 12), width=207, height=169, fg_color="#dddddd", corner_radius=10
        )
        self.lbl_foto_autorizado.pack(pady=(10, 5))
        self.lbl_foto_autorizado.bind("<Button-1>", lambda e: self.capturar_y_comparar_foto())
        def cargar_foto():
            self.photo_path = filedialog.askopenfilename(
                title="Seleccionar Foto",
                filetypes=[("Archivos de Imagen", "*.png;*.jpg;*.jpeg")]
            )
            if self.photo_path:
                # Cargar y redimensionar la imagen
                img = Image.open(self.photo_path)
                img = img.resize((200, 200))  # Tamaño mediano para la vista previa
                self.photo_preview = ctk.CTkImage(img)
                lbl_foto.configure(image=self.photo_preview, text="")  # Mostrar la imagen

        lbl_foto = ctk.CTkLabel(self.content, text="No se ha cargado ninguna foto", font=("Arial", 12))
        lbl_foto.pack(pady=(10, 5))


        # Botón Realizar Registro
        btn_guardar = ctk.CTkButton(
            self.content,
            text="Realizar Registro",
            fg_color="#6A0DAD",
            hover_color="#5A0CA0",
            text_color="white",
            width=180,
            height=45,
            font=("Arial", 14, "bold"),
            corner_radius=10,
            command=self.guardar_registro
        )
        btn_guardar.pack(anchor="w", padx=70, pady=30)

    def guardar_registro(self):
        datos = [entry.get() for entry in self.entry_fields.values()]

        if any(dato.strip() == "" for dato in datos if dato != "Entrada"):
            messagebox.showwarning("Campos vacíos", "Por favor, llena todos los campos.")
            return

        if not hasattr(self, "foto_cv2") or not hasattr(self, "encoding_actual"):
            messagebox.showwarning("Faltan datos", "Toma una foto antes de guardar.")
            return

        # Guardar en el nuevo esquema: personas (VISITANTE), empresas, motivos, areas, visitas y foto
        nombre, empresa_nombre, motivo_nombre, apellido, area_nombre, _entrada = (
            datos[0], datos[1], datos[2], datos[3], datos[4], datos[5]
        )

        empresa_id = get_or_create_empresa(empresa_nombre)
        motivo_id = get_or_create_motivo(motivo_nombre)
        area_id = get_or_create_area(area_nombre)
        persona_id = get_or_create_persona("VISITANTE", nombre, apellido, empresa_id)

        # Insertar visita
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO visitas (persona_id, motivo_id, area_id) VALUES (?,?,?)",
            (persona_id, motivo_id, area_id)
        )
        visita_id = cur.lastrowid

        # Guardar foto como evidencia y asociarla a la visita
        _, buffer = cv2.imencode('.jpg', self.foto_cv2)
        foto_blob = buffer.tobytes()
        conn.commit()
        conn.close()

        foto_id = insertar_foto(persona_id=persona_id, visita_id=visita_id, imagen_blob=foto_blob, tipo="EVIDENCIA")

        # Asignar evidencia principal a la visita
        conn2 = get_conn()
        cur2 = conn2.cursor()
        try:
            cur2.execute(
                "UPDATE visitas SET evidencia_principal_foto_id=? WHERE id=?",
                (foto_id, visita_id)
            )
            conn2.commit()
        finally:
            conn2.close()

        messagebox.showinfo("Éxito", "Registro guardado correctamente.")
        self.mostrar_lista_registro()

    def ver_foto_grande(self, ruta_imagen):
        ventana_foto = ctk.CTkToplevel(self)
        ventana_foto.title("Foto en grande")
        ventana_foto.geometry("600x600")  # Aumenté el tamaño de la ventana

        # Cargar imagen
        img = Image.open(ruta_imagen)

        # Ajustar tamaño para que llene la ventana, pero manteniendo proporciones
        img.thumbnail((550, 550))  # Cambia el tamaño pero respeta la proporción
        img_ctk = ctk.CTkImage(img, size=img.size)

        lbl_img = ctk.CTkLabel(ventana_foto, image=img_ctk, text="")
        lbl_img.image = img_ctk
        lbl_img.pack(expand=True, fill="both", padx=10, pady=10)

    def mostrar_base_datos(self):
        for widget in self.content.winfo_children():
            widget.destroy()

        title = ctk.CTkLabel(self.content, text="Base de datos (Personal autorizado)", font=("Arial", 22, "bold"))
        title.pack(anchor="nw", padx=30, pady=(20, 10))

        btn_nuevo = ctk.CTkButton(
            self.content, text="Nuevo autorizado", fg_color="#6A0DAD", text_color="white",
            hover_color="#5A0CA0", corner_radius=8, width=140,
            command=self.mostrar_formulario_autorizado
        )

        btn_nuevo.pack(anchor="ne", padx=30)

        tabla = ctk.CTkScrollableFrame(self.content, height=450, fg_color="#f5f5f5", corner_radius=10)
        tabla.pack(fill="both", expand=True, padx=30, pady=10)

        columnas = ["Foto", "Nombre", "Apellido", "Empresa", "Actividad empresarial", "🗑️"]

        for i, texto in enumerate(columnas):
            etiqueta = ctk.CTkLabel(tabla, text=texto, font=("Arial", 13, "bold"), text_color="black",
                                    fg_color="#cde4f9", width=120, anchor="center")
            etiqueta.grid(row=0, column=i, padx=1, pady=1)

        conn = get_conn()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT p.id, p.nombre, p.apellido,
                   IFNULL(e.nombre,''), IFNULL(e.actividad,''),
                   (
                       SELECT imagen_blob FROM fotos f
                       WHERE f.persona_id = p.id
                       ORDER BY tomada_en DESC LIMIT 1
                   ) AS foto_blob
            FROM personas p
            LEFT JOIN empresas e ON e.id = p.empresa_id
            WHERE p.tipo = 'AUTORIZADO'
            ORDER BY p.creado_en DESC
            """
        )
        autorizados = cursor.fetchall()
        conn.close()

        for r, fila in enumerate(autorizados, start=1):
            foto_blob = fila[5]  # Campo 'foto' como BLOB
            if foto_blob:
                try:
                    imagen = Image.open(io.BytesIO(foto_blob))
                    imagen.thumbnail((80, 80))  # Miniatura
                    imagen_ctk = ctk.CTkImage(imagen)

                    lbl_imagen = ctk.CTkLabel(tabla, image=imagen_ctk, text="", cursor="hand2")
                    lbl_imagen.image = imagen_ctk
                    lbl_imagen.grid(row=r, column=0, padx=1, pady=1)

                    def mostrar_grande(blob=foto_blob):
                        img_grande = Image.open(io.BytesIO(blob))
                        img_grande.thumbnail((500, 500))  # Ajustar tamaño grande
                        img_ctk = ctk.CTkImage(img_grande, size=img_grande.size)

                        ventana = ctk.CTkToplevel(self)
                        ventana.title("Foto en grande")
                        ventana.transient(self)  # Se coloca delante de la ventana principal
                        ventana.grab_set()  # Modal: bloquea la ventana principal hasta cerrar esta
                        ventana.focus_set()  # Pone foco en la ventana emergente

                        lbl = ctk.CTkLabel(ventana, image=img_ctk, text="")
                        lbl.image = img_ctk
                        lbl.pack(padx=20, pady=20)

                    lbl_imagen.bind("<Button-1>", lambda e, b=foto_blob: mostrar_grande(b))

                except Exception as e:
                    lbl_imagen = ctk.CTkLabel(tabla, text="Error Img", fg_color="#eeeeee")
                    lbl_imagen.grid(row=r, column=0, padx=1, pady=1)
            else:
                lbl_imagen = ctk.CTkLabel(tabla, text="Sin foto", fg_color="#eeeeee")
                lbl_imagen.grid(row=r, column=0, padx=1, pady=1)

            # Resto de columnas
            for c in range(1, len(columnas) - 1):
                valor = fila[c]
                cell = ctk.CTkLabel(tabla, text=valor, font=("Arial", 12), text_color="black",
                                    width=120, fg_color="#eeeeee")
                cell.grid(row=r, column=c, padx=1, pady=1)

            # Botón eliminar
            def eliminar_persona(id_persona=fila[0]):
                if messagebox.askyesno("Confirmar", "¿Eliminar este autorizado?"):
                    conn = get_conn()
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM personas WHERE id=?", (id_persona,))
                    conn.commit()
                    conn.close()
                    messagebox.showinfo("Eliminado", "Personal eliminado exitosamente.")
                    self.mostrar_base_datos()

            btn_eliminar = ctk.CTkButton(tabla, text="❌", width=40, height=30, font=("Arial", 14),
                                         fg_color="#ff4d4d", hover_color="#ff1a1a",
                                         text_color="white", corner_radius=5,
                                         command=eliminar_persona)
            btn_eliminar.grid(row=r, column=len(columnas) - 1, padx=1, pady=1)

    def mostrar_formulario_autorizado(self):
        for widget in self.content.winfo_children():
            widget.destroy()

        title = ctk.CTkLabel(self.content, text="Nuevo Personal Autorizado", font=("Arial", 22, "bold"))
        title.pack(anchor="nw", padx=30, pady=(20, 10))

        form_frame = ctk.CTkFrame(self.content, fg_color="white")
        form_frame.pack(pady=10)

        campos = ["Nombre", "Apellido", "Empresa", "Actividad empresarial"]
        self.entry_autorizado = {}

        for i, campo in enumerate(campos):
            lbl = ctk.CTkLabel(form_frame, text=campo, font=("Arial", 14), anchor="w", width=200)
            lbl.grid(row=i, column=0, sticky="w", padx=10, pady=5)
            entry = ctk.CTkEntry(form_frame, width=300)
            entry.grid(row=i, column=1, padx=10, pady=5)
            self.entry_autorizado[campo] = entry

        # Foto desde cámara
        self.lbl_foto_autorizado = ctk.CTkLabel(
            self.content,
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
            self.content, text="Guardar", fg_color="#4CAF50", hover_color="#45a049",
            text_color="white", width=140, corner_radius=10,
            command=self.guardar_autorizado
        )
        btn_guardar.pack(pady=20)

    def guardar_autorizado(self):
        datos = [entry.get() for entry in self.entry_autorizado.values()]

        if any(dato.strip() == "" for dato in datos):
            messagebox.showwarning("Campos vacíos", "Por favor completa todos los campos.")
            return

        if not hasattr(self, "foto_cv2") or not hasattr(self, "encoding_actual"):
            messagebox.showwarning("Faltan datos", "Toma una foto antes de guardar.")
            return

        nombre, apellido, empresa_nombre, actividad = datos
        empresa_id = get_or_create_empresa(empresa_nombre, actividad)
        persona_id = get_or_create_persona("AUTORIZADO", nombre, apellido, empresa_id)

        # Guardar encoding y foto
        insertar_encoding(persona_id, self.encoding_actual)
        _, buffer = cv2.imencode('.jpg', self.foto_cv2)
        foto_blob = buffer.tobytes()
        insertar_foto(persona_id=persona_id, imagen_blob=foto_blob, tipo="ROSTRO")

        messagebox.showinfo("Éxito", "Nuevo personal autorizado guardado.")
        self.mostrar_base_datos()

    def mostrar_lista_registro(self):
        for widget in self.content.winfo_children():
            widget.destroy()

        title = ctk.CTkLabel(self.content, text="Lista de Registro", font=("Arial", 22, "bold"))
        title.pack(anchor="nw", padx=30, pady=(20, 10))

        # ---------------- NUEVO: BOTÓN PARA NUEVO REGISTRO ----------------
        btn_nuevo_registro = ctk.CTkButton(
            self.content, text="Nuevo Registro", fg_color="#6A0DAD", text_color="white",
            hover_color="#5A0CA0", corner_radius=8, width=140,
            command=self.mostrar_formulario_registro
        )

        btn_nuevo_registro.pack(anchor="ne", padx=30, pady=(0, 20))
        # ------------------------------------------------------------------

        tabla = ctk.CTkScrollableFrame(self.content, height=450, fg_color="#f5f5f5", corner_radius=10)
        tabla.pack(fill="both", expand=True, padx=30, pady=10)

        columnas = ["Nombre", "Apellido", "Empresa", "Motivo", "Área", "Entrada", "Salida", "🗑️"]

        for i, texto in enumerate(columnas):
            etiqueta = ctk.CTkLabel(tabla, text=texto, font=("Arial", 13, "bold"), text_color="black",
                                    fg_color="#cde4f9", width=100, anchor="center")
            etiqueta.grid(row=0, column=i, padx=1, pady=1)

        conn = get_conn()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT v.id,
                   p.nombre,
                   p.apellido,
                   IFNULL(e.nombre,''),
                   IFNULL(mv.nombre,''),
                   IFNULL(a.nombre,''),
                   v.hora_entrada,
                   IFNULL(v.hora_salida, '')
            FROM visitas v
            JOIN personas p ON p.id = v.persona_id
            LEFT JOIN empresas e ON e.id = p.empresa_id
            LEFT JOIN motivos_visita mv ON mv.id = v.motivo_id
            LEFT JOIN areas a ON a.id = v.area_id
            ORDER BY v.hora_entrada DESC
            """
        )
        registros = cursor.fetchall()
        conn.close()

        for r, fila in enumerate(registros, start=1):
            for c in range(len(columnas)):
                if c < 6:
                    # Mostrar Nombre, Apellido, Empresa, Motivo, Área, Entrada
                    valor = fila[c + 1]
                    cell = ctk.CTkLabel(tabla, text=valor, font=("Arial", 12), text_color="black",
                                        width=100, fg_color="#eeeeee")
                    cell.grid(row=r, column=c, padx=1, pady=1)

                elif c == 6:
                    # Columna de Salida → Botón o mostrar hora
                    hora_salida = fila[7]

                    if hora_salida == "" or hora_salida is None:
                        # Botón para registrar salida
                        def registrar_salida(id_registro=fila[0]):
                            hora_actual = datetime.now().strftime("%I:%M %p")
                            conn = get_conn()
                            cursor = conn.cursor()
                            cursor.execute("UPDATE visitas SET hora_salida = ? WHERE id = ?",
                                           (hora_actual, id_registro))
                            conn.commit()
                            conn.close()
                            messagebox.showinfo("Salida registrada", "La hora de salida ha sido registrada.")
                            self.mostrar_lista_registro()

                        btn_salida = ctk.CTkButton(tabla, text="Registrar salida", fg_color="#4CAF50",
                                                   text_color="white", hover_color="#45a049",
                                                   width=120, height=30, corner_radius=5,
                                                   command=registrar_salida)
                        btn_salida.grid(row=r, column=c, padx=1, pady=1)
                    else:
                        # Mostrar hora de salida en color verde
                        lbl_salida = ctk.CTkLabel(tabla, text=f"{hora_salida}", font=("Arial", 12, "bold"),
                                                  text_color="#4CAF50", width=100, fg_color="#eeeeee")
                        lbl_salida.grid(row=r, column=c, padx=1, pady=1)

                elif c == 7:
                    # Última columna → Botón eliminar registro
                    def eliminar_registro(id_registro=fila[0]):
                        if messagebox.askyesno("Confirmar", "¿Eliminar este registro?"):
                            conn = get_conn()
                            cursor = conn.cursor()
                            cursor.execute("DELETE FROM visitas WHERE id=?", (id_registro,))
                            conn.commit()
                            conn.close()
                            messagebox.showinfo("Eliminado", "Registro eliminado.")
                            self.mostrar_lista_registro()

                    btn_eliminar = ctk.CTkButton(tabla, text="❌", width=40, height=30, font=("Arial", 14),
                                                 fg_color="#ff4d4d", hover_color="#ff1a1a",
                                                 text_color="white", corner_radius=5,
                                                 command=eliminar_registro)
                    btn_eliminar.grid(row=r, column=c, padx=1, pady=1)


def validar_usuario(usuario, contrasena):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id FROM usuarios_admin WHERE username=? AND password_hash=? AND activo=1",
        (usuario, contrasena)
    )
    row = cursor.fetchone()
    usuario_id = row[0] if row else None

    # Registrar sesión
    try:
        exito = 1 if usuario_id else 0
        cursor.execute(
            "INSERT INTO sesiones_usuario (usuario_id, exito, ip_origen) VALUES (?, ?, ?)",
            (usuario_id if usuario_id else None, exito, None)
        )
        conn.commit()
    except Exception:
        # Si falla el log de sesión, continuar sin bloquear el login
        pass
    finally:
        conn.close()

    return usuario_id is not None




def mostrar_login():
    ctk.set_appearance_mode("light")
    ctk.set_default_color_theme("blue")

    # Asegurar DB y usuario por defecto
    ensure_db_exists()
    ensure_default_admin()

    login = ctk.CTk(fg_color="white")
    login.title("Login")
    login.geometry("1300x700")
    login.resizable(False, False)

    frame = ctk.CTkFrame(login, fg_color="white", corner_radius=20)
    frame.place(relx=0.5, rely=0.5, anchor="center")

    user_icon = load_ctk_image("user_icon_lavanda_rounded.png", (120, 120))
    icon_label = ctk.CTkLabel(frame, image=user_icon, text="", fg_color="transparent")
    icon_label.pack(pady=(40, 20))

    entry_user = ctk.CTkEntry(frame, placeholder_text="Usuario", width=300, height=40, corner_radius=10)
    entry_user.pack(pady=10)

    entry_pass = ctk.CTkEntry(frame, placeholder_text="Contraseña", show="*", width=300, height=40, corner_radius=10)
    entry_pass.pack(pady=10)

    def iniciar_sesion():
        usuario = entry_user.get()
        contrasena = entry_pass.get()

        if validar_usuario(usuario, contrasena):
            login.destroy()
            menu = MenuPrincipal()
            menu.mainloop()
        else:
            messagebox.showerror("Error", "Usuario o contraseña incorrectos.")

    btn_login = ctk.CTkButton(
        frame, text="Ingresar", fg_color="#6A0DAD", hover_color="#5A0CA0",
        text_color="white", width=140, height=40, corner_radius=20, command=iniciar_sesion
    )
    btn_login.pack(pady=(20, 40))

    login.mainloop()

# Iniciar aplicación
if __name__ == "__main__":
    mostrar_login()