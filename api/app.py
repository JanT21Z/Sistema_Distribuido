from flask import Flask, jsonify, request, abort
from database import db_connection
from services import generate_pan, validate_dpi, send_sms_record
from sms_service import send_to_queue


app = Flask(__name__)

@app.route('/tarjeta-credito', methods=['POST'])
def create_card():
    data = request.get_json()
    conn, cursor = db_connection()

    try:
        # Validar datos requeridos
        if not all(key in data for key in ('nombre', 'apellido', 'edad', 'direccion', 'dpi', 'telefono', 'limite_credito')):
            abort(400, "Datos faltantes.")

        # Validar DPI único
        if not validate_dpi(cursor, data['dpi']):
            abort(400, "El DPI ya está asociado a una tarjeta.")

        # Crear cliente y tarjeta
        pan = generate_pan()
        cursor.execute("""
            INSERT INTO Cliente (Nombre, Apellido, Edad, Direccion, DPI, Telefono) 
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (data['nombre'], data['apellido'], data['edad'], data['direccion'], data['dpi'], data['telefono']))
        cliente_id = cursor.lastrowid

        cursor.execute("""
            INSERT INTO Tarjeta_Credito (PAN, ID_Cliente, Limite_Credito, Saldo_Actual, Saldo_Disponible, Estado, Replica_Origen)
            VALUES (%s, %s, %s, 0.00, %s, 'Activa', %s)
        """, (pan, cliente_id, data['limite_credito'], data['limite_credito'], request.host))
        conn.commit()

        # Notificar creación
        message = f"Tarjeta creada exitosamente para el cliente {data['nombre']} {data['apellido']}. PAN: {pan}"
        send_to_queue(message)

        return jsonify({'mensaje': 'Tarjeta creada exitosamente.', 'PAN': pan}), 201
    except Exception as e:
        conn.rollback()
        print(f"Error en create_card: {e}")
        abort(500, "Error interno del servidor")
    finally:
        conn.close()

@app.route('/tarjeta-credito', methods=['GET'])
def get_all_cards():
    conn, cursor = db_connection()

    try:
        cursor.execute("SELECT * FROM Tarjeta_Credito")
        cards = cursor.fetchall()
        return jsonify(cards), 200
    except Exception as e:
        print(f"Error en get_all_cards: {e}")
        abort(500, "Error interno del servidor")
    finally:
        conn.close()

@app.route('/tarjeta-credito/<pan>', methods=['GET'])
def get_card_by_pan(pan):
    """
    Obtener información de una tarjeta de crédito por su PAN.
    """
    conn, cursor = db_connection()

    try:
        cursor.execute("SELECT * FROM Tarjeta_Credito WHERE PAN = %s", (pan,))
        card = cursor.fetchone()

        if not card:
            abort(404, "Tarjeta no encontrada.")

        return jsonify(card), 200
    except Exception as e:
        print(f"Error en get_card_by_pan: {e}")
        abort(500, "Error interno del servidor")
    finally:
        conn.close()

@app.route('/tarjeta-credito/<pan>', methods=['PUT'])
def update_card(pan):
    """
    Modificar los datos de una tarjeta de crédito.
    """
    data = request.get_json()
    conn, cursor = db_connection()

    try:
        # Validar si la tarjeta existe
        cursor.execute("SELECT * FROM Tarjeta_Credito WHERE PAN = %s", (pan,))
        card = cursor.fetchone()

        if not card:
            abort(404, "Tarjeta no encontrada.")

        # Validar datos requeridos para modificar
        fields = []
        values = []

        if 'limite_credito' in data:
            fields.append("Limite_Credito = %s")
            values.append(data['limite_credito'])
        if 'estado' in data:
            fields.append("Estado = %s")
            values.append(data['estado'])

        if not fields:
            abort(400, "No se proporcionaron datos para actualizar.")

        # Construir la consulta dinámicamente
        query = f"UPDATE Tarjeta_Credito SET {', '.join(fields)} WHERE PAN = %s"
        values.append(pan)
        cursor.execute(query, tuple(values))
        conn.commit()

        return jsonify({'mensaje': 'Tarjeta actualizada exitosamente.'}), 200
    except Exception as e:
        conn.rollback()
        print(f"Error en update_card: {e}")
        abort(500, f"Error interno del servidor: {str(e)}")
    finally:
        conn.close()

@app.route('/tarjeta-credito/procesamiento/<pan>', methods=['POST'])
def process_charge(pan):
    """
    Realiza un cargo a la tarjeta de crédito.
    """
    data = request.get_json()
    conn, cursor = db_connection()

    try:
        cursor.execute("""
            SELECT tc.ID_Tarjeta, tc.Saldo_Disponible, c.Telefono
            FROM Tarjeta_Credito tc
            JOIN Cliente c ON tc.ID_Cliente = c.ID_Cliente
            WHERE tc.PAN = %s
        """, (pan,))
        card = cursor.fetchone()

        if not card:
            abort(404, "Tarjeta no encontrada.")

        if card['Saldo_Disponible'] < data['monto']:
            abort(400, "Fondos insuficientes.")

        # Actualizar saldo
        cursor.execute("""
            UPDATE Tarjeta_Credito
            SET Saldo_Actual = Saldo_Actual + %s, Saldo_Disponible = Saldo_Disponible - %s
            WHERE PAN = %s
        """, (data['monto'], data['monto'], pan))

        # Registrar la transacción
        cursor.execute("""
            INSERT INTO Transacciones (PAN, Tipo, Monto, Detalle)
            VALUES (%s, 'Cargo', %s, %s)
        """, (pan, data['monto'], data['detalle']))

        # Registrar SMS
        send_sms_record(
            cursor=cursor,
            id_tarjeta=card['ID_Tarjeta'],
            telefono=card['Telefono'],
            mensaje=f"Cargo realizado por Q{data['monto']}. Detalle: {data['detalle']}"
        )

        conn.commit()
        return jsonify({'mensaje': 'Cargo realizado exitosamente.'}), 200

    except Exception as e:
        conn.rollback()
        print(f"Error en process_charge: {e}")
        abort(500, f"Error interno del servidor: {str(e)}")
    finally:
        conn.close()



@app.route('/tarjeta-credito/abono/<pan>', methods=['POST'])
def process_payment(pan):
    """
    Realiza un abono a la tarjeta de crédito.
    """
    data = request.get_json()
    conn, cursor = db_connection()

    try:
        # Obtener datos de la tarjeta y cliente
        cursor.execute("""
            SELECT tc.ID_Tarjeta, tc.Saldo_Actual, c.Telefono
            FROM Tarjeta_Credito tc
            JOIN Cliente c ON tc.ID_Cliente = c.ID_Cliente
            WHERE tc.PAN = %s
        """, (pan,))
        card = cursor.fetchone()

        if not card:
            abort(404, "Tarjeta no encontrada.")

        # Validar que el saldo sea suficiente
        if card['Saldo_Actual'] < data['monto']:
            abort(400, "No se puede abonar más de lo debido.")

        # Actualizar saldos
        cursor.execute("""
            UPDATE Tarjeta_Credito
            SET Saldo_Actual = Saldo_Actual - %s, Saldo_Disponible = Saldo_Disponible + %s
            WHERE PAN = %s
        """, (data['monto'], data['monto'], pan))

        # Registrar la transacción
        cursor.execute("""
            INSERT INTO Transacciones (PAN, Tipo, Monto, Detalle)
            VALUES (%s, 'Abono', %s, %s)
        """, (pan, data['monto'], data['detalle']))

        # Registrar SMS
        send_sms_record(
            cursor=cursor,
            id_tarjeta=card['ID_Tarjeta'],  # Aquí puede estar el problema
            telefono=card['Telefono'],
            mensaje=f"Abono realizado por Q{data['monto']}. Detalle: {data['detalle']}"
        )

        conn.commit()
        return jsonify({'mensaje': 'Abono realizado exitosamente.'}), 200

    except Exception as e:
        conn.rollback()
        print(f"Error en process_payment: {e}")
        abort(500, f"Error interno del servidor: {str(e)}")
    finally:
        conn.close()



@app.route('/tarjeta-credito/balance/<pan>', methods=['GET'])
def get_balance(pan):
    """
    Obtener el balance de una tarjeta de crédito por su PAN.
    """
    conn, cursor = db_connection()

    try:
        # Validar que la tarjeta exista
        cursor.execute("SELECT Limite_Credito, Saldo_Actual, Saldo_Disponible FROM Tarjeta_Credito WHERE PAN = %s", (pan,))
        card = cursor.fetchone()

        if not card:
            abort(404, "Tarjeta no encontrada.")

        # Responder con el balance
        return jsonify({
            'limite_credito': card['Limite_Credito'],
            'saldo_actual': card['Saldo_Actual'],
            'saldo_disponible': card['Saldo_Disponible']
        }), 200
    except Exception as e:
        print(f"Error en get_balance: {e}")
        abort(500, "Error interno del servidor.")
    finally:
        conn.close()


@app.route('/tarjeta-credito/<pan>', methods=['DELETE'])
def delete_card(pan):
    """
    Eliminar una tarjeta de crédito por su PAN.
    """
    conn, cursor = db_connection()

    try:
        # Validar si la tarjeta existe
        cursor.execute("SELECT Saldo_Actual FROM Tarjeta_Credito WHERE PAN = %s", (pan,))
        card = cursor.fetchone()

        if not card:
            abort(404, "Tarjeta no encontrada.")

        # Validar que la tarjeta no tenga saldo pendiente
        if card['Saldo_Actual'] > 0:
            abort(400, "No se puede eliminar una tarjeta con saldo pendiente.")

        # Eliminar la tarjeta
        cursor.execute("DELETE FROM Tarjeta_Credito WHERE PAN = %s", (pan,))
        conn.commit()

        return jsonify({'mensaje': 'Tarjeta eliminada exitosamente.'}), 200
    except Exception as e:
        conn.rollback()
        print(f"Error en delete_card: {e}")
        abort(500, f"Error interno del servidor: {str(e)}")
    finally:
        conn.close()



if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
