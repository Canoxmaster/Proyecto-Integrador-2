import sqlite3

DB_NAME = "control_visitas.db"

def main():
    conn = sqlite3.connect(DB_NAME)
    conn.execute("PRAGMA foreign_keys = ON;")
    cur = conn.cursor()

    # --- Limpieza (DROP) en orden seguro para FKs ---
    drops = [
        "DROP TABLE IF EXISTS reconocimientos",
        "DROP TABLE IF EXISTS dispositivos",
        "DROP TABLE IF EXISTS eventos_sistema",
        "DROP TABLE IF EXISTS visita_eventos",
        "DROP TABLE IF EXISTS fotos",
        "DROP TABLE IF EXISTS visitas",
        "DROP TABLE IF EXISTS facial_encodings",
        "DROP TABLE IF EXISTS personas",
        "DROP TABLE IF EXISTS motivos_visita",
        "DROP TABLE IF EXISTS areas",
        "DROP TABLE IF EXISTS empresas",
        "DROP TABLE IF EXISTS sesiones_usuario",
        "DROP TABLE IF EXISTS usuarios_admin",
    ]
    for d in drops:
        cur.execute(d)

    # ============================================================
    # 1) usuarios_admin
    # ============================================================
    cur.execute("""
    CREATE TABLE usuarios_admin (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        nombre TEXT NOT NULL,
        rol TEXT NOT NULL DEFAULT 'ADMIN',
        activo INTEGER NOT NULL DEFAULT 1,
        creado_en TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP),
        CHECK (rol IN ('ADMIN','OPERADOR','SUPERVISOR')),
        CHECK (activo IN (0,1))
    );
    """)

    # ============================================================
    # 2) sesiones_usuario
    # ============================================================
    cur.execute("""
    CREATE TABLE sesiones_usuario (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id INTEGER NOT NULL,
        inicio_sesion TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP),
        fin_sesion TEXT,
        ip_origen TEXT,            -- IPv4/IPv6
        exito INTEGER NOT NULL DEFAULT 1,
        FOREIGN KEY (usuario_id) REFERENCES usuarios_admin(id) ON DELETE CASCADE,
        CHECK (exito IN (0,1))
    );
    """)

    # ============================================================
    # 3) empresas
    # ============================================================
    cur.execute("""
    CREATE TABLE empresas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL UNIQUE,
        actividad TEXT
    );
    """)

    # ============================================================
    # 4) areas
    # ============================================================
    cur.execute("""
    CREATE TABLE areas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL UNIQUE,
        descripcion TEXT
    );
    """)

    # ============================================================
    # 5) motivos_visita
    # ============================================================
    cur.execute("""
    CREATE TABLE motivos_visita (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL UNIQUE,
        descripcion TEXT
    );
    """)

    # ============================================================
    # 6) personas (VISITANTE/AUTORIZADO)
    # ============================================================
    cur.execute("""
    CREATE TABLE personas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tipo TEXT NOT NULL,
        nombre TEXT NOT NULL,
        apellido TEXT,
        empresa_id INTEGER,
        cargo_rol TEXT,
        activo INTEGER NOT NULL DEFAULT 1,
        creado_en TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP),
        CHECK (tipo IN ('VISITANTE','AUTORIZADO')),
        CHECK (activo IN (0,1)),
        FOREIGN KEY (empresa_id) REFERENCES empresas(id)
    );
    """)

    # ============================================================
    # 7) facial_encodings (1:N con personas)
    # ============================================================
    cur.execute("""
    CREATE TABLE facial_encodings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        persona_id INTEGER NOT NULL,
        encoding_vector BLOB NOT NULL,   -- o TEXT si lo guardarás en base64
        creado_en TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP),
        FOREIGN KEY (persona_id) REFERENCES personas(id) ON DELETE CASCADE
    );
    """)

    # ============================================================
    # 8) fotos (puede referir a persona y/o visita)
    #    (Se crea ANTES de visitas para ayudar con la circularidad)
    # ============================================================
    cur.execute("""
    CREATE TABLE fotos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        persona_id INTEGER,
        visita_id INTEGER,
        ruta_archivo TEXT,
        imagen_blob BLOB,
        tomada_en TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP),
        tipo TEXT,  -- 'ROSTRO','EVIDENCIA','OTRO'
        FOREIGN KEY (persona_id) REFERENCES personas(id) ON DELETE SET NULL
        -- FK a visitas(visita_id) se define después de crear visitas
    );
    """)

    # ============================================================
    # 9) visitas (encabezado)
    #    Nota: evidencia_principal_foto_id NO puede tener FK directa
    #    por la circularidad; se emula con TRIGGERS abajo.
    # ============================================================
    cur.execute("""
    CREATE TABLE visitas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        persona_id INTEGER NOT NULL,     -- normalmente VISITANTE
        motivo_id INTEGER,
        area_id INTEGER,
        registrado_por INTEGER,          -- admin/operador
        hora_entrada TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP),
        hora_salida TEXT,
        comentario TEXT,
        evidencia_principal_foto_id INTEGER, -- se valida por triggers
        FOREIGN KEY (persona_id) REFERENCES personas(id),
        FOREIGN KEY (motivo_id) REFERENCES motivos_visita(id),
        FOREIGN KEY (area_id) REFERENCES areas(id),
        FOREIGN KEY (registrado_por) REFERENCES usuarios_admin(id)
    );
    """)

    # Ahora que visitas existe, agregamos la FK de fotos.visita_id -> visitas.id
    cur.execute("""
    PRAGMA foreign_keys = OFF;
    """)
    # En SQLite no se puede "ALTER TABLE ... ADD CONSTRAINT" para FKs,
    # pero sí podemos crear la FK si recreáramos la tabla. Para evitar eso,
    # lo que hacemos es asegurar integridad desde el lado de 'fotos' con triggers.
    # (Alternativamente, podrías recrear 'fotos' aquí con la FK explícita).
    cur.execute("""
    PRAGMA foreign_keys = ON;
    """)

    # Trigger para asegurar que evidencia_principal_foto_id exista en fotos
    cur.execute("""
    CREATE TRIGGER IF NOT EXISTS trg_visitas_evidencia_insert
    BEFORE INSERT ON visitas
    WHEN NEW.evidencia_principal_foto_id IS NOT NULL
    BEGIN
        SELECT
            CASE
                WHEN (SELECT id FROM fotos WHERE id = NEW.evidencia_principal_foto_id) IS NULL
                THEN RAISE(ABORT, 'evidencia_principal_foto_id no existe en fotos')
            END;
    END;
    """)

    cur.execute("""
    CREATE TRIGGER IF NOT EXISTS trg_visitas_evidencia_update
    BEFORE UPDATE OF evidencia_principal_foto_id ON visitas
    WHEN NEW.evidencia_principal_foto_id IS NOT NULL
    BEGIN
        SELECT
            CASE
                WHEN (SELECT id FROM fotos WHERE id = NEW.evidencia_principal_foto_id) IS NULL
                THEN RAISE(ABORT, 'evidencia_principal_foto_id no existe en fotos')
            END;
    END;
    """)

    # Si se borra una foto que era evidencia principal de una visita, poner NULL
    cur.execute("""
    CREATE TRIGGER IF NOT EXISTS trg_fotos_delete_null_visitas
    AFTER DELETE ON fotos
    BEGIN
        UPDATE visitas
           SET evidencia_principal_foto_id = NULL
         WHERE evidencia_principal_foto_id = OLD.id;
    END;
    """)

    # (Opcional) integridad visita_id en fotos con visitas: emular FK con triggers
    cur.execute("""
    CREATE TRIGGER IF NOT EXISTS trg_fotos_visita_insert
    BEFORE INSERT ON fotos
    WHEN NEW.visita_id IS NOT NULL
    BEGIN
        SELECT
            CASE
                WHEN (SELECT id FROM visitas WHERE id = NEW.visita_id) IS NULL
                THEN RAISE(ABORT, 'visita_id no existe en visitas')
            END;
    END;
    """)
    cur.execute("""
    CREATE TRIGGER IF NOT EXISTS trg_fotos_visita_update
    BEFORE UPDATE OF visita_id ON fotos
    WHEN NEW.visita_id IS NOT NULL
    BEGIN
        SELECT
            CASE
                WHEN (SELECT id FROM visitas WHERE id = NEW.visita_id) IS NULL
                THEN RAISE(ABORT, 'visita_id no existe en visitas')
            END;
    END;
    """)

    # Si se borra una visita, eliminar sus fotos (CASCADE manual)
    cur.execute("""
    CREATE TRIGGER IF NOT EXISTS trg_visitas_delete_cascade_fotos
    AFTER DELETE ON visitas
    BEGIN
        DELETE FROM fotos WHERE visita_id = OLD.id;
    END;
    """)

    # ============================================================
    # 10) visita_eventos (detalle)
    # ============================================================
    cur.execute("""
    CREATE TABLE visita_eventos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        visita_id INTEGER NOT NULL,
        tipo_evento TEXT NOT NULL,  -- 'ENTRADA','SALIDA','ACTUALIZACION','ELIMINACION'
        generado_por INTEGER,       -- usuario admin
        descripcion TEXT,
        creado_en TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP),
        CHECK (tipo_evento IN ('ENTRADA','SALIDA','ACTUALIZACION','ELIMINACION')),
        FOREIGN KEY (visita_id) REFERENCES visitas(id) ON DELETE CASCADE,
        FOREIGN KEY (generado_por) REFERENCES usuarios_admin(id)
    );
    """)

    # ============================================================
    # 11) eventos_sistema
    # ============================================================
    cur.execute("""
    CREATE TABLE eventos_sistema (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        actor_tipo TEXT NOT NULL,      -- 'ADMIN','AUTORIZADO'
        actor_id INTEGER,              -- usuarios_admin.id o personas.id
        accion TEXT NOT NULL,          -- 'LOGIN','ALTA_AUTORIZADO', etc.
        detalle TEXT,
        creado_en TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP),
        CHECK (actor_tipo IN ('ADMIN','AUTORIZADO'))
    );
    """)

    # ============================================================
    # 13) dispositivos
    # ============================================================
    cur.execute("""
    CREATE TABLE dispositivos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL UNIQUE,
        ubicacion TEXT,
        activo INTEGER NOT NULL DEFAULT 1,
        creado_en TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP),
        CHECK (activo IN (0,1))
    );
    """)

    # ============================================================
    # 14) reconocimientos
    # ============================================================
    cur.execute("""
    CREATE TABLE reconocimientos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        dispositivo_id INTEGER,
        persona_id INTEGER,    -- si se identificó
        exito INTEGER NOT NULL,
        umbral REAL,
        distancia REAL,
        capturado_en TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP),
        visita_id INTEGER,
        FOREIGN KEY (dispositivo_id) REFERENCES dispositivos(id),
        FOREIGN KEY (persona_id) REFERENCES personas(id),
        FOREIGN KEY (visita_id) REFERENCES visitas(id),
        CHECK (exito IN (0,1))
    );
    """)

    # ============================================================
    # Índices útiles (incluye índices parciales)
    # ============================================================
    # personas(tipo) parcial AUTORIZADO
    cur.execute("""
    CREATE INDEX idx_personas_autorizado
    ON personas (tipo)
    WHERE tipo = 'AUTORIZADO';
    """)
    cur.execute("CREATE INDEX idx_visitas_persona ON visitas(persona_id);")
    cur.execute("CREATE INDEX idx_visitas_entrada ON visitas(hora_entrada);")
    cur.execute("CREATE INDEX idx_facial_persona ON facial_encodings(persona_id);")
    cur.execute("CREATE INDEX idx_fotos_visita ON fotos(visita_id);")
    cur.execute("CREATE INDEX idx_eventos_visita ON visita_eventos(visita_id);")

    conn.commit()
    conn.close()
    print("Esquema SQLite creado en", DB_NAME)

if __name__ == "__main__":
    main()
