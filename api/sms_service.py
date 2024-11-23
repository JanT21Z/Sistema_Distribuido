import pika

def send_to_queue(message):
    """
    Envía un mensaje a la cola de RabbitMQ.
    :param message: Mensaje a enviar.
    """
    try:
        # Conexión al servidor RabbitMQ
        connection = pika.BlockingConnection(pika.ConnectionParameters(host='host.docker.internal'))
        channel = connection.channel()

        # Declarar la cola (asegurarse de que existe)
        channel.queue_declare(queue='sms_queue', durable=True)

        # Enviar mensaje
        channel.basic_publish(
            exchange='',
            routing_key='sms_queue',
            body=message,
            properties=pika.BasicProperties(
                delivery_mode=2  # Hacer que el mensaje sea persistente
            )
        )
        print(f"Mensaje enviado a la cola: {message}")

        connection.close()
    except Exception as e:
        print(f"Error al enviar mensaje a RabbitMQ: {e}")


def send_test_message():
    """
    Envía un mensaje de prueba a la cola de RabbitMQ.
    """
    try:
        test_message = "Mensaje de prueba para verificar conexión con RabbitMQ."
        send_to_queue(test_message)
        print("Mensaje de prueba enviado correctamente.")
    except Exception as e:
        print(f"Error al enviar el mensaje de prueba: {e}")


# Si se ejecuta el archivo directamente, envía un mensaje de prueba
if __name__ == "__main__":
    send_test_message()
