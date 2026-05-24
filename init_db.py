# init_db.py
import sqlite3
from werkzeug.security import generate_password_hash

def init_database():
    conn = sqlite3.connect('instance/cookies.db') # Flask crea la carpeta instance por defecto
    cursor = conn.cursor()

    # 1. Tabla de Usuarios (Administradores)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')

    # 2. Tabla de Productos (Cookies)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS product (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            price REAL NOT NULL,
            image_url TEXT,
            active INTEGER DEFAULT 1
        )
    ''')

    # 3. Tabla de Pedidos
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cookie_order (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_number TEXT UNIQUE NOT NULL,
            customer_name TEXT NOT NULL,
            address TEXT NOT NULL,
            phone TEXT NOT NULL,
            notes TEXT,
            total REAL NOT NULL,
            status TEXT DEFAULT 'Recibido',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 4. Tabla de Detalles del Pedido (Relación muchos a muchos)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS order_item (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            price REAL NOT NULL,
            FOREIGN KEY (order_id) REFERENCES cookie_order(id),
            FOREIGN KEY (product_id) REFERENCES product(id)
        )
    ''')

    # Crear usuario administrador por defecto si no existe
    cursor.execute("SELECT * FROM user WHERE username = 'admin'")
    if not cursor.fetchone():
        # Contraseña segura: 'cookie123'
        hashed_password = generate_password_hash('cookie123')
        cursor.execute("INSERT INTO user (username, password) VALUES (?, ?)", ('admin', hashed_password))
        print("¡Usuario administrador creado con éxito! (User: admin | Pass: cookie123)")

    conn.commit()
    conn.close()

if __name__ == '__main__':
    import os
    if not os.path.exists('instance'):
        os.makedirs('instance')
    init_database()