import os
import sqlite3
import hashlib
from typing import Optional, List, Tuple, Any, Dict
from typing import Iterable

DB_NAME = "control_visitas.db"


def get_conn():
    conn = sqlite3.connect(DB_NAME)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def ensure_db_exists():
    try:
        if not os.path.exists(DB_NAME):
            try:
                import Codigo_db
                Codigo_db.main()
            except Exception:
                pass
    except Exception:
        pass


def ensure_default_admin():
    conn = get_conn()
    cur = conn.cursor()
    try:
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


def _table_has_column(cur, table: str, column: str) -> bool:
    cur.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cur.fetchall())


def ensure_soft_delete_columns():
    """Add 'activo INTEGER NOT NULL DEFAULT 1' to empresas/areas/motivos_visita if missing."""
    conn = get_conn()
    cur = conn.cursor()
    try:
        for table in ("empresas", "areas", "motivos_visita"):
            try:
                if not _table_has_column(cur, table, "activo"):
                    cur.execute(f"ALTER TABLE {table} ADD COLUMN activo INTEGER NOT NULL DEFAULT 1")
                    cur.execute(f"UPDATE {table} SET activo=1 WHERE activo IS NULL")
            except sqlite3.OperationalError:
                # Table may not exist yet; ignore during first boot
                pass
        conn.commit()
    finally:
        conn.close()


def ensure_default_catalogs():
    """Ensure default Area='Recepción' and Motivo='Visita' exist to allow camera-only auto-fill."""
    conn = get_conn()
    cur = conn.cursor()
    try:
        # Área Recepción
        cur.execute("SELECT id FROM areas WHERE lower(nombre)=lower(?)", ("Recepción",))
        if cur.fetchone() is None:
            cur.execute("INSERT INTO areas (nombre, descripcion) VALUES (?, ?)", ("Recepción", "Área por defecto para visitas"))
        # Motivo Visita
        cur.execute("SELECT id FROM motivos_visita WHERE lower(nombre)=lower(?)", ("Visita",))
        if cur.fetchone() is None:
            cur.execute("INSERT INTO motivos_visita (nombre, descripcion) VALUES (?, ?)", ("Visita", "Motivo por defecto de visitas"))
        conn.commit()
    finally:
        conn.close()


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ---------- Auth ----------

def authenticate(username: str, password: str) -> Optional[int]:
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id, password_hash, activo FROM usuarios_admin WHERE username=?", (username,))
        row = cur.fetchone()
        if not row:
            _log_session(cur, None, False)
            conn.commit()
            return None
        user_id, stored_hash, activo = row
        if not activo:
            _log_session(cur, user_id, False)
            conn.commit()
            return None
        # Permitir compatibilidad con hash o texto plano ya existente
        ok = (stored_hash == password) or (stored_hash == sha256(password))
        _log_session(cur, user_id, ok)
        conn.commit()
        return user_id if ok else None
    finally:
        conn.close()


def _log_session(cur, user_id: Optional[int], ok: bool):
    cur.execute(
        "INSERT INTO sesiones_usuario (usuario_id, exito, ip_origen) VALUES (?,?,?)",
        (user_id, 1 if ok else 0, None)
    )


# ---------- Catálogos: empresas, áreas, motivos ----------

def list_empresas() -> List[Tuple[Any, ...]]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, nombre, IFNULL(actividad,'') FROM empresas WHERE activo=1 ORDER BY nombre")
    rows = cur.fetchall()
    conn.close()
    return rows


def create_empresa(nombre: str, actividad: Optional[str] = None) -> int:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("INSERT INTO empresas (nombre, actividad) VALUES (?, ?)", (nombre, actividad))
    eid = cur.lastrowid
    conn.commit()
    conn.close()
    return eid


def delete_empresa(emp_id: int):
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("UPDATE empresas SET activo=0 WHERE id=?", (emp_id,))
    except sqlite3.OperationalError:
        cur.execute("DELETE FROM empresas WHERE id=?", (emp_id,))
    conn.commit()
    conn.close()


def list_areas():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, nombre, IFNULL(descripcion,'') FROM areas WHERE activo=1 ORDER BY nombre")
    rows = cur.fetchall()
    conn.close()
    return rows


def create_area(nombre: str, descripcion: Optional[str] = None) -> int:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("INSERT INTO areas (nombre, descripcion) VALUES (?, ?)", (nombre, descripcion))
    aid = cur.lastrowid
    conn.commit()
    conn.close()
    return aid


def delete_area(area_id: int):
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("UPDATE areas SET activo=0 WHERE id=?", (area_id,))
    except sqlite3.OperationalError:
        cur.execute("DELETE FROM areas WHERE id=?", (area_id,))
    conn.commit()
    conn.close()


def list_motivos():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, nombre, IFNULL(descripcion,'') FROM motivos_visita WHERE activo=1 ORDER BY nombre")
    rows = cur.fetchall()
    conn.close()
    return rows


def create_motivo(nombre: str, descripcion: Optional[str] = None) -> int:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("INSERT INTO motivos_visita (nombre, descripcion) VALUES (?, ?)", (nombre, descripcion))
    mid = cur.lastrowid
    conn.commit()
    conn.close()
    return mid


def delete_motivo(motivo_id: int):
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("UPDATE motivos_visita SET activo=0 WHERE id=?", (motivo_id,))
    except sqlite3.OperationalError:
        cur.execute("DELETE FROM motivos_visita WHERE id=?", (motivo_id,))
    conn.commit()
    conn.close()


def list_motivos_activos() -> List[Tuple[int, str]]:
    """Return active motivos (id, nombre). Falls back to all if 'activo' column doesn't exist yet."""
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id, nombre FROM motivos_visita WHERE activo=1 ORDER BY nombre")
    except sqlite3.OperationalError:
        cur.execute("SELECT id, nombre FROM motivos_visita ORDER BY nombre")
    rows = cur.fetchall()
    conn.close()
    return rows


def get_motivo_sugerencias(persona_id: int, max_items: int = 5) -> List[Tuple[int, str]]:
    """Suggest motivos for a person: last used first, then most frequent for that person (unique list)."""
    conn = get_conn()
    cur = conn.cursor()
    sugeridos: List[Tuple[int, str]] = []
    usados: set[int] = set()
    try:
        # Último motivo usado
        cur.execute(
            """
            SELECT mv.id, mv.nombre
            FROM visitas v
            JOIN motivos_visita mv ON mv.id = v.motivo_id
            WHERE v.persona_id = ? AND v.motivo_id IS NOT NULL
            ORDER BY v.id DESC
            LIMIT 1
            """,
            (persona_id,)
        )
        row = cur.fetchone()
        if row:
            sugeridos.append((row[0], row[1]))
            usados.add(row[0])

        # Más frecuentes para esa persona
        cur.execute(
            """
            SELECT mv.id, mv.nombre, COUNT(*) as cnt
            FROM visitas v
            JOIN motivos_visita mv ON mv.id = v.motivo_id
            WHERE v.persona_id = ? AND v.motivo_id IS NOT NULL
            GROUP BY mv.id, mv.nombre
            ORDER BY cnt DESC
            LIMIT ?
            """,
            (persona_id, max_items)
        )
        for mid, nombre, _ in cur.fetchall():
            if mid not in usados:
                sugeridos.append((mid, nombre))
                usados.add(mid)
            if len(sugeridos) >= max_items:
                break
    finally:
        conn.close()
    return sugeridos


def list_motivos_activos():
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id, nombre FROM motivos_visita WHERE activo=1 ORDER BY nombre;")
    except sqlite3.OperationalError:
        # Si aún no existe 'activo', devolver todos
        cur.execute("SELECT id, nombre FROM motivos_visita ORDER BY nombre;")
    rows = cur.fetchall()
    conn.close()
    return [{"id": r[0], "nombre": r[1]} for r in rows]


def get_motivo_sugerencias(persona_id: int, max_items: int = 5):
    conn = get_conn()
    cur = conn.cursor()

    # Último motivo usado por la persona
    cur.execute("""
        SELECT mv.id, mv.nombre
        FROM visitas v
        JOIN motivos_visita mv ON mv.id = v.motivo_id
        WHERE v.persona_id = ? AND v.motivo_id IS NOT NULL
        ORDER BY v.id DESC
        LIMIT 1
    """, (persona_id,))
    last = cur.fetchone()
    sugeridos = []
    usados = set()
    if last:
        sugeridos.append({"id": last[0], "nombre": last[1]})
        usados.add(last[0])

    # Más frecuentes para esa persona (excluyendo el último si ya está)
    cur.execute("""
        SELECT mv.id, mv.nombre, COUNT(*) AS cnt
        FROM visitas v
        JOIN motivos_visita mv ON mv.id = v.motivo_id
        WHERE v.persona_id = ? AND v.motivo_id IS NOT NULL
        GROUP BY mv.id, mv.nombre
        ORDER BY cnt DESC
        LIMIT ?
    """, (persona_id, max_items))
    for mid, nombre, _ in cur.fetchall():
        if mid not in usados:
            sugeridos.append({"id": mid, "nombre": nombre})
            usados.add(mid)
        if len(sugeridos) >= max_items:
            break

    conn.close()
    return sugeridos


# ---------- Personas y biometría ----------

def list_personas(tipo: Optional[str] = None):
    conn = get_conn()
    cur = conn.cursor()
    if tipo:
        cur.execute(
            """
            SELECT p.id, p.tipo, p.nombre, IFNULL(p.apellido,''), IFNULL(e.nombre,''), IFNULL(p.cargo_rol,''), p.activo
            FROM personas p
            LEFT JOIN empresas e ON e.id = p.empresa_id
            WHERE p.tipo = ? AND p.activo = 1
            ORDER BY p.creado_en DESC
            """,
            (tipo,)
        )
    else:
        cur.execute(
            """
            SELECT p.id, p.tipo, p.nombre, IFNULL(p.apellido,''), IFNULL(e.nombre,''), IFNULL(p.cargo_rol,''), p.activo
            FROM personas p
            LEFT JOIN empresas e ON e.id = p.empresa_id
            WHERE p.activo = 1
            ORDER BY p.creado_en DESC
            """
        )
    rows = cur.fetchall()
    conn.close()
    return rows


def create_persona(tipo: str, nombre: str, apellido: Optional[str], empresa_id: Optional[int], cargo_rol: Optional[str]) -> int:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO personas (tipo, nombre, apellido, empresa_id, cargo_rol) VALUES (?,?,?,?,?)",
        (tipo, nombre, apellido, empresa_id, cargo_rol)
    )
    pid = cur.lastrowid
    conn.commit()
    conn.close()
    return pid


def delete_persona(persona_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE personas SET activo=0 WHERE id=?", (persona_id,))
    conn.commit()
    conn.close()


def add_persona_encoding(persona_id: int, encoding_blob: bytes):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("INSERT INTO facial_encodings (persona_id, encoding_vector) VALUES (?, ?)", (persona_id, encoding_blob))
    conn.commit()
    conn.close()


def add_persona_foto(persona_id: int, imagen_blob: bytes, visita_id: Optional[int] = None, tipo: str = "ROSTRO") -> int:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO fotos (persona_id, visita_id, imagen_blob, tipo) VALUES (?,?,?,?)",
        (persona_id, visita_id, imagen_blob, tipo)
    )
    fid = cur.lastrowid
    conn.commit()
    conn.close()
    return fid


def list_autorizados_encodings():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT p.id, p.nombre, IFNULL(p.apellido,''), IFNULL(e.nombre,''), fe.encoding_vector
        FROM personas p
        JOIN facial_encodings fe ON fe.persona_id = p.id
        LEFT JOIN empresas e ON e.id = p.empresa_id
        WHERE p.tipo='AUTORIZADO' AND p.activo=1 AND fe.encoding_vector IS NOT NULL
        """
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def get_persona_empresa_id(persona_id: int) -> Optional[int]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT empresa_id FROM personas WHERE id=?", (persona_id,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None


def get_persona_ultima_foto(persona_id: int) -> Optional[bytes]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT imagen_blob
        FROM fotos
        WHERE persona_id=? AND imagen_blob IS NOT NULL
        ORDER BY tomada_en DESC
        LIMIT 1
        """,
        (persona_id,)
    )
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None


# ---------- Visitas ----------

def list_visitas(limit: int = 200):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT v.id, p.nombre, IFNULL(p.apellido,''), IFNULL(e.nombre,''), IFNULL(mv.nombre,''), IFNULL(a.nombre,''), v.hora_entrada, IFNULL(v.hora_salida,'')
        FROM visitas v
        JOIN personas p ON p.id = v.persona_id
        LEFT JOIN empresas e ON e.id = p.empresa_id
        LEFT JOIN motivos_visita mv ON mv.id = v.motivo_id
        LEFT JOIN areas a ON a.id = v.area_id
        ORDER BY v.hora_entrada DESC LIMIT ?
        """,
        (limit,)
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def create_visita(persona_id: int, motivo_id: Optional[int], area_id: Optional[int], registrado_por: Optional[int]) -> int:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO visitas (persona_id, motivo_id, area_id, registrado_por) VALUES (?,?,?,?)",
        (persona_id, motivo_id, area_id, registrado_por)
    )
    vid = cur.lastrowid
    conn.commit()
    conn.close()
    return vid


def set_visita_salida(visita_id: int, hora_salida: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE visitas SET hora_salida=? WHERE id=?", (hora_salida, visita_id))
    conn.commit()
    conn.close()


def delete_visita(visita_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM visitas WHERE id=?", (visita_id,))
    conn.commit()
    conn.close()


def set_visita_evidencia_principal(visita_id: int, foto_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE visitas SET evidencia_principal_foto_id=? WHERE id=?", (foto_id, visita_id))
    conn.commit()
    conn.close()


def insertar_foto_visita(visita_id: int, imagen: Any, persona_id: Optional[int] = None, tipo: str = "EVIDENCIA") -> int:
    """Insert a photo linked to a visit. Accepts either raw bytes (JPEG) or a numpy BGR image.
    Returns the new foto id.
    """
    # Try to detect if imagen is already bytes
    blob: Optional[bytes] = None
    try:
        if isinstance(imagen, (bytes, bytearray, memoryview)):
            blob = bytes(imagen)
        else:
            # Attempt OpenCV encode if numpy array
            try:
                import numpy as _np  # local import to avoid hard dependency in module import time
                import cv2 as _cv2
                if hasattr(imagen, 'shape') and hasattr(imagen, 'dtype'):
                    ok, buf = _cv2.imencode('.jpg', imagen)
                    if ok:
                        blob = buf.tobytes()
            except Exception:
                blob = None
    except Exception:
        blob = None
    if blob is None:
        raise ValueError("imagen debe ser bytes JPEG o un frame numpy compatible con OpenCV")

    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO fotos (persona_id, visita_id, imagen_blob, tipo) VALUES (?,?,?,?)",
        (persona_id, visita_id, blob, tipo)
    )
    fid = cur.lastrowid
    conn.commit()
    conn.close()
    return fid


def get_latest_visita_defaults(persona_id: int) -> Tuple[Optional[int], Optional[int]]:
    """Return (motivo_id, area_id) from the most recent visit of the person, if any."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT motivo_id, area_id FROM visitas WHERE persona_id=? ORDER BY id DESC LIMIT 1",
        (persona_id,)
    )
    row = cur.fetchone()
    conn.close()
    if row:
        return row[0], row[1]
    return None, None


def get_open_visita_for_persona(persona_id: int) -> Optional[int]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT id FROM visitas WHERE persona_id=? AND hora_salida IS NULL ORDER BY id DESC LIMIT 1",
        (persona_id,)
    )
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None


# ---------- Dispositivos y reconocimientos ----------

def list_dispositivos():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, nombre, IFNULL(ubicacion,''), activo FROM dispositivos WHERE activo=1 ORDER BY nombre")
    rows = cur.fetchall()
    conn.close()
    return rows


def create_dispositivo(nombre: str, ubicacion: Optional[str] = None) -> int:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("INSERT INTO dispositivos (nombre, ubicacion) VALUES (?, ?)", (nombre, ubicacion))
    did = cur.lastrowid
    conn.commit()
    conn.close()
    return did


def delete_dispositivo(dispositivo_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE dispositivos SET activo=0 WHERE id=?", (dispositivo_id,))
    conn.commit()
    conn.close()


def update_dispositivo(dispositivo_id: int, nombre: str, ubicacion: Optional[str], activo: bool):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "UPDATE dispositivos SET nombre=?, ubicacion=?, activo=? WHERE id=?",
        (nombre, ubicacion, 1 if activo else 0, dispositivo_id)
    )
    conn.commit()
    conn.close()


def create_reconocimiento(dispositivo_id: Optional[int], persona_id: Optional[int], exito: bool, umbral: Optional[float], distancia: Optional[float], visita_id: Optional[int] = None) -> int:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO reconocimientos (dispositivo_id, persona_id, exito, umbral, distancia, visita_id) VALUES (?,?,?,?,?,?)",
        (dispositivo_id, persona_id, 1 if exito else 0, umbral, distancia, visita_id)
    )
    rid = cur.lastrowid
    conn.commit()
    conn.close()
    return rid


# ---------- Eventos del sistema ----------

def log_event(actor_tipo: str, actor_id: Optional[int], accion: str, detalle: Optional[str] = None):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO eventos_sistema (actor_tipo, actor_id, accion, detalle) VALUES (?,?,?,?)",
        (actor_tipo, actor_id, accion, detalle)
    )
    conn.commit()
    conn.close()


def list_eventos(limit: int = 300):
    return search_eventos(limit=limit)


def search_eventos(fecha_inicio: Optional[str] = None, fecha_fin: Optional[str] = None,
                   actor_tipo: Optional[str] = None, actor_id: Optional[int] = None,
                   texto: Optional[str] = None, limit: int = 500):
    conn = get_conn()
    cur = conn.cursor()
    query = [
        "SELECT id, actor_tipo, IFNULL(actor_id,''), accion, IFNULL(detalle,''), creado_en",
        "FROM eventos_sistema WHERE 1=1"
    ]
    params: List[Any] = []
    if actor_tipo:
        query.append("AND actor_tipo = ?")
        params.append(actor_tipo)
    if actor_id is not None:
        query.append("AND actor_id = ?")
        params.append(actor_id)
    if fecha_inicio:
        query.append("AND datetime(creado_en) >= datetime(?)")
        params.append(fecha_inicio)
    if fecha_fin:
        query.append("AND datetime(creado_en) <= datetime(?)")
        params.append(fecha_fin)
    if texto:
        query.append("AND (accion LIKE ? OR detalle LIKE ?)")
        like = f"%{texto}%"
        params.extend([like, like])
    query.append("ORDER BY id DESC LIMIT ?")
    params.append(limit)
    cur.execute(" ".join(query), params)
    rows = cur.fetchall()
    conn.close()
    return rows


def list_sesiones(limit: int = 300):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT s.id, u.username, s.inicio_sesion, IFNULL(s.fin_sesion,''), s.exito, IFNULL(s.ip_origen,'')
        FROM sesiones_usuario s
        LEFT JOIN usuarios_admin u ON u.id = s.usuario_id
        ORDER BY s.id DESC LIMIT ?
        """,
        (limit,)
    )
    rows = cur.fetchall()
    conn.close()
    return rows
