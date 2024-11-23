import pika

def callback(ch, method, properties, body):
    print(f"Mensaje recibido: {body.decode()}")

def main():
    connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
    channel = connection.channel()
    channel.queue_declare(queue='sms_queue', durable=True)
    channel.basic_consume(queue='sms_queue', on_message_callback=callback, auto_ack=True)

    print("Esperando mensajes. Presiona CTRL+C para salir.")
    channel.start_consuming()

if __name__ == '__main__':
    main()
