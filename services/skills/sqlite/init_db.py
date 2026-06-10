import os
import sqlite3

# Definir rutas absolutas
db_dir = r"c:\temp\AI Local\services\skills\sqlite"
db_path = os.path.join(db_dir, "inventario.db")

# Asegurar existencia de directorio
os.makedirs(db_dir, exist_ok=True)

# Limpiar archivo previo para creación pura
if os.path.exists(db_path):
    try:
        os.remove(db_path)
    except PermissionError:
        print(f"Error: La base de datos en {db_path} está en uso. Cierre las conexiones antes de re-inicializar.")
        exit(1)

# Conectar y estructurar base de datos
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 1. Crear tabla de productos
cursor.execute('''
    CREATE TABLE productos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL,
        categoria TEXT NOT NULL,
        precio REAL NOT NULL,
        stock INTEGER NOT NULL
    )
''')

# 2. Insertar registros iniciales de prueba
productos = [
    ("Servidor NAS Synology", "Almacenamiento", 450.00, 12),
    ("Disco Duro Red Pro 8TB", "Almacenamiento", 220.50, 45),
    ("Switch TP-Link 24 Puertos", "Redes", 110.00, 8),
    ("Router WiFi 6 ASUS", "Redes", 189.99, 15),
    ("Cámara de Seguridad IP", "Seguridad", 75.25, 30)
]

cursor.executemany(
    "INSERT INTO productos (nombre, categoria, precio, stock) VALUES (?, ?, ?, ?)",
    productos
)

conn.commit()
conn.close()

print(f"¡Base de datos SQLite inicializada exitosamente en: {db_path}!")
