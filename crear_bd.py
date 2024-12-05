import sqlite3
import os
from werkzeug.security import generate_password_hash

# Función para crear y conectar la base de datos
def conectar_bd():
    db_path = os.path.join(os.path.dirname(__file__), 'cuentas_por_pagar.db')
    return sqlite3.connect(db_path)

# Función para crear las tablas en la base de datos
def crear_bd():
    conn = conectar_bd()
    cursor = conn.cursor()

    # Crear la tabla de proveedores si no existe
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS proveedores (
            id_proveedor INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            balance REAL NOT NULL DEFAULT 0
        )
    ''')

    # Crear la tabla de transacciones si no existe
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transacciones (
            id_transaccion INTEGER PRIMARY KEY AUTOINCREMENT,
            id_proveedor INTEGER NOT NULL,
            tipo_movimiento TEXT NOT NULL CHECK(tipo_movimiento IN ('CR', 'DB')),
            monto REAL NOT NULL,
            FOREIGN KEY (id_proveedor) REFERENCES proveedores (id_proveedor)
        )
    ''')

    # Crear la tabla de facturas si no existe
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS facturas (
            id_factura INTEGER PRIMARY KEY AUTOINCREMENT,
            id_proveedor INTEGER NOT NULL,
            monto REAL NOT NULL,
            descripcion TEXT,
            fecha_emision DATE NOT NULL,
            fecha_vencimiento DATE NOT NULL,
            FOREIGN KEY (id_proveedor) REFERENCES proveedores (id_proveedor)
        )
    ''')

    # Crear la tabla de usuarios (ya que está en el contexto original)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('admin', 'user'))
        )
    ''')

    conn.commit()
    conn.close()

# Función para insertar registros iniciales
def insertar_registros_iniciales():
    conn = conectar_bd()
    cursor = conn.cursor()
    
    # Insertar proveedores iniciales
    proveedores = [
        ("1", "Proveedor A", "2600"),
        ("2", "Proveedor B", "3500")
    ]
    
    cursor.executemany('''
        INSERT OR IGNORE INTO proveedores (id_proveedor, nombre, balance) 
        VALUES (?, ?, ?)
    ''', proveedores)
    
    # Insertar transacciones iniciales
    transacciones = [
        (1, 1, 'CR', 1500.00),
        (2, 2, 'DB', 500.00)
    ]
    
    cursor.executemany('''
        INSERT INTO transacciones (id_transaccion, id_proveedor, tipo_movimiento, monto)
        VALUES (?, ?, ?, ?)
    ''', transacciones)

    # Insertar usuarios iniciales
    admin_username = "admin"
    admin_password = generate_password_hash("admin123")
    admin_role = "admin"

    user_username = "user"
    user_password = generate_password_hash("user123")
    user_role = "user"

    cursor.execute('''
        INSERT OR IGNORE INTO usuarios (username, password, role) 
        VALUES (?, ?, ?)
    ''', (admin_username, admin_password, admin_role))

    cursor.execute('''
        INSERT OR IGNORE INTO usuarios (username, password, role) 
        VALUES (?, ?, ?)
    ''', (user_username, user_password, user_role))

    # Insertar facturas iniciales
    facturas = [
        (1, 1, 1000.00, "Compra de insumos", "2024-01-01", "2024-01-15"),
        (2, 2, 2000.00, "Servicios contratados", "2024-01-10", "2024-01-20")
    ]

    cursor.executemany('''
        INSERT OR IGNORE INTO facturas (id_factura, id_proveedor, monto, descripcion, fecha_emision, fecha_vencimiento)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', facturas)

    conn.commit()
    conn.close()
    print("Registros iniciales insertados en las tablas.")

# Ejecuta la creación de tablas y la inserción de datos iniciales
if __name__ == "__main__":
    crear_bd()
    insertar_registros_iniciales()

