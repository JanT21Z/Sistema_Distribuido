from database import db_connection

def get_all_cards():
    """Obtener todas las tarjetas de crédito."""
    conn, cursor = db_connection()
    cursor.execute("SELECT * FROM Tarjeta_Credito")
    cards = cursor.fetchall()
    conn.close()
    return cards

def get_card_by_pan(pan):
    """Obtener una tarjeta de crédito por su número PAN."""
    conn, cursor = db_connection()
    cursor.execute("SELECT * FROM Tarjeta_Credito WHERE PAN = %s", (pan,))
    card = cursor.fetchone()
    conn.close()
    return card

def create_transaction(pan, tipo, monto, detalle=None):
    """Registrar una transacción en la base de datos."""
    conn, cursor = db_connection()
    cursor.execute("""
        SELECT Saldo_Actual, Limite_Credito FROM Tarjeta_Credito WHERE PAN = %s
    """, (pan,))
    card = cursor.fetchone()

    if not card:
        return False, "Tarjeta no encontrada."

    nuevo_saldo = card['Saldo_Actual'] + monto if tipo == 'Abono' else card['Saldo_Actual'] - monto

    if nuevo_saldo < 0:
        return False, "Fondos insuficientes."

    if nuevo_saldo > card['Limite_Credito']:
        return False, "Límite de crédito excedido."

    # Actualizar el saldo de la tarjeta
    cursor.execute("""
        UPDATE Tarjeta_Credito SET Saldo_Actual = %s WHERE PAN = %s
    """, (nuevo_saldo, pan))

    # Insertar la transacción
    cursor.execute("""
        INSERT INTO Transaccion (ID_Tarjeta, Tipo, Monto, Detalle)
        SELECT ID_Tarjeta, %s, %s, %s FROM Tarjeta_Credito WHERE PAN = %s
    """, (tipo, monto, detalle, pan))

    conn.commit()
    conn.close()
    return True, "Transacción registrada exitosamente."
