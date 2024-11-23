import mysql.connector
import os

def db_connection():
    """Establecer conexión a la base de datos."""
    try:
        conn = mysql.connector.connect(
            host=os.getenv("DB_HOST", "host.docker.internal"),
            port=int(os.getenv("DB_PORT", 3306)),
            user=os.getenv("DB_USER", "root"),
            password=os.getenv("DB_PASSWORD", ""),
            database=os.getenv("DB_NAME", "sistema_tarjetas")
        )
        cursor = conn.cursor(dictionary=True)
        return conn, cursor
    except mysql.connector.Error as err:
        print(f"Error al conectar a la base de datos: {err}")
        raise
