import sqlite3

# Conectar o crear la base de datos
conn = sqlite3.connect('acceso.db')
cursor = conn.cursor()

# ------------------ Tabla de usuarios ------------------
cursor.execute('''
CREATE TABLE IF NOT EXISTS usuarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario TEXT NOT NULL,
    contrasena TEXT NOT NULL
)
''')

# Insertar usuario por defecto si no existe
cursor.execute("SELECT COUNT(*) FROM usuarios WHERE usuario = ?", ("admin",))
if cursor.fetchone()[0] == 0:
    cursor.execute("INSERT INTO usuarios (usuario, contrasena) VALUES (?, ?)", ("admin", "1234"))
    print("Usuario 'admin' agregado con contraseña '1234'.")

# ------------------ Tabla de personal autorizado ------------------
cursor.execute('''
CREATE TABLE IF NOT EXISTS personal_autorizado (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL,
    apellido TEXT NOT NULL,
    empresa TEXT NOT NULL,
    actividad TEXT NOT NULL,
    foto BLOB,
    encoding BLOB
)
''')

print("Tablas creadas correctamente.")
conn.commit()
conn.close()
