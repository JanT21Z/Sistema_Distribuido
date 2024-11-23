import random
import mysql.connector

def generate_pan():
    """
    Generar un número de tarjeta único con el prefijo 6800.
    """
    return '6800' + ''.join(str(random.randint(0, 9)) for _ in range(12))

def validate_dpi(cursor, dpi):
    """
    Validar si un DPI ya está registrado en la base de datos.
    :param cursor: Cursor de conexión a la base de datos.
    :param dpi: DPI del cliente.
    :return: True si el DPI no está registrado, False en caso contrario.
    """
    cursor.execute("SELECT 1 FROM Cliente WHERE DPI = %s", (dpi,))
    return cursor.fetchone() is None

def calculate_balance(cursor, pan):
    """
    Calcular el balance de una tarjeta de crédito.
    :param cursor: Cursor de conexión a la base de datos.
    :param pan: Número de tarjeta de crédito (PAN).
    :return: Diccionario con los detalles del balance o None si no se encuentra la tarjeta.
    """
    cursor.execute("SELECT Limite_Credito, Saldo_Actual FROM Tarjeta_Credito WHERE PAN = %s", (pan,))
    card = cursor.fetchone()

    if not card:
        return None

    return {
        'limite_credito': card['Limite_Credito'],
        'saldo_actual': card['Saldo_Actual'],
        'saldo_disponible': card['Limite_Credito'] - card['Saldo_Actual']
    }

def send_sms_record(cursor, id_tarjeta, telefono, mensaje, id_cola="RabbitMQ"):
    """
    Registrar un SMS en la base de datos.
    :param cursor: Cursor de conexión a la base de datos.
    :param id_tarjeta: ID de la tarjeta a la que pertenece el mensaje.
    :param telefono: Número de teléfono del destinatario.
    :param mensaje: Mensaje de texto a enviar.
    :param id_cola: Identificador de la cola (por defecto RabbitMQ).
    """
    try:
        cursor.execute("""
            INSERT INTO SMS (ID_Tarjeta, Telefono, Mensaje, Estado, ID_Cola)
            VALUES (%s, %s, %s, 'Pendiente', %s)
        """, (id_tarjeta, telefono, mensaje, id_cola))
    except mysql.connector.Error as err:
        print(f"Error al registrar el SMS: {err}")
        raise Exception("Error al registrar el SMS en la base de datos.")
