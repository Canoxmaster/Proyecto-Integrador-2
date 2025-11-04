import customtkinter as ctk
from tkinter import messagebox
import face_recognition
import numpy as np
import cv2
from ...camera import camera
from ... import db

class ReconocimientosPage(ctk.CTkFrame):
    def __init__(self, parent, current_user_id: int):
        super().__init__(parent, corner_radius=0)
        self.configure(fg_color="white")
        self.current_user_id = current_user_id

        title = ctk.CTkLabel(self, text="Reconocimientos faciales", font=("Arial", 22, "bold"))
        title.pack(anchor="w", padx=24, pady=(20, 10))

        form = ctk.CTkFrame(self, fg_color="#f7f7f7")
        form.pack(fill="x", padx=24, pady=8)

        # Dispositivo (texto libre, vínculo opcional)
        self.e_disp = ctk.CTkEntry(form, placeholder_text="Nombre del dispositivo", width=280)
        self.e_disp.pack(side="left", padx=8, pady=10)
        ctk.CTkButton(form, text="Iniciar reconocimiento", fg_color="#6A0DAD", hover_color="#5A0CA0", command=self._run_recognition).pack(side="left", padx=8)

        info = ctk.CTkLabel(self, text="Se abrirá la cámara. Presiona 'Espacio' para capturar, 'Esc' para salir.")
        info.pack(anchor="w", padx=24, pady=(0,6))

        self.table = ctk.CTkScrollableFrame(self, height=520)
        self.table.pack(fill="both", expand=True, padx=24, pady=8)

        self.refresh()

    def refresh(self):
        for w in self.table.winfo_children():
            w.destroy()
        headers = ["ID", "Dispositivo", "Persona", "Éxito", "Distancia", "Capturado"]
        for i, h in enumerate(headers):
            ctk.CTkLabel(self.table, text=h, font=("Arial", 13, "bold"), fg_color="#e9eef6", width=160).grid(row=0, column=i, padx=2, pady=2)
        # Consulta simple (últimos 50)
        conn = db.get_conn()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT r.id, IFNULL(d.nombre,''), IFNULL(p.nombre,''), r.exito, IFNULL(r.distancia,''), r.capturado_en
            FROM reconocimientos r
            LEFT JOIN dispositivos d ON d.id = r.dispositivo_id
            LEFT JOIN personas p ON p.id = r.persona_id
            ORDER BY r.id DESC LIMIT 50
            """
        )
        rows = cur.fetchall()
        conn.close()
        for r, (rid, disp, persona, exito, dist, ts) in enumerate(rows, start=1):
            values = [rid, disp, persona, "Sí" if exito else "No", f"{dist:.3f}" if isinstance(dist, float) else dist, ts]
            for c, v in enumerate(values):
                ctk.CTkLabel(self.table, text=v, font=("Arial", 12), fg_color="#f5f5f5", width=160).grid(row=r, column=c, padx=2, pady=2)

    def _run_recognition(self):
        disp_name = self.e_disp.get().strip()
        dispositivo_id = None
        if disp_name:
            match = [d for d in db.list_dispositivos() if d[1].lower() == disp_name.lower()]
            dispositivo_id = match[0][0] if match else db.create_dispositivo(disp_name)

        if not camera.open():
            messagebox.showerror("Cámara", "No se pudo abrir la cámara")
            return
        messagebox.showinfo("Reconocimiento", "Presiona 'Espacio' para capturar, 'Esc' para salir")

        # precargar encodings autorizados
        registros = db.list_autorizados_encodings()
        known_encodings = [(pid, np.frombuffer(enc, dtype=np.float64), f"{nom}") for (pid, nom, ape, emp, enc) in registros]

        while True:
            ret, frame = camera.read()
            if not ret:
                break
            cv2.imshow("Reconocimiento", frame)
            key = cv2.waitKey(1)
            if key % 256 == 27:
                cv2.destroyAllWindows()
                break
            elif key % 256 == 32:
                # procesar captura
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                encs = face_recognition.face_encodings(rgb)
                if not encs:
                    messagebox.showwarning("Rostro", "No se detectó rostro")
                    continue
                enc = encs[0]
                # comparar
                if not known_encodings:
                    rid = db.create_reconocimiento(dispositivo_id, None, exito=False, umbral=0.5, distancia=None, visita_id=None)
                    messagebox.showinfo("Resultado", "No hay encodings para comparar")
                else:
                    distances = [face_recognition.face_distance([ke[1]], enc)[0] for ke in known_encodings]
                    idx = int(np.argmin(distances))
                    best_dist = float(distances[idx])
                    umbral = 0.5
                    if best_dist <= umbral:
                        persona_id = known_encodings[idx][0]
                        rid = db.create_reconocimiento(dispositivo_id, persona_id, exito=True, umbral=umbral, distancia=best_dist)
                        messagebox.showinfo("Reconocido", f"Persona ID {persona_id} (dist {best_dist:.3f})")
                    else:
                        rid = db.create_reconocimiento(dispositivo_id, None, exito=False, umbral=umbral, distancia=best_dist)
                        messagebox.showinfo("No reconocido", f"Mejor distancia {best_dist:.3f} > {umbral}")
                cv2.destroyAllWindows()
                break
        self.refresh()
