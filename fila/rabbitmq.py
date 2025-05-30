import pika
import json
import os

class RabbitMQ:
    def __init__(self, fila_nome):
        self.fila_nome = fila_nome
        self.connection = pika.BlockingConnection(pika.ConnectionParameters(
            host=os.getenv("RABBITMQ_HOST", "localhost")
        ))
        self.channel = self.connection.channel()
        self.channel.queue_declare(queue=fila_nome, durable=True)

    def enviar(self, mensagem: dict):
        corpo = json.dumps(mensagem)
        self.channel.basic_publish(
            exchange='',
            routing_key=self.fila_nome,
            body=corpo,
            properties=pika.BasicProperties(delivery_mode=2)
        )

    def consumir(self, callback):
        def wrapper(ch, method, properties, body):
            dados = json.loads(body)
            callback(dados)
            ch.basic_ack(delivery_tag=method.delivery_tag)

        self.channel.basic_qos(prefetch_count=1)
        self.channel.basic_consume(queue=self.fila_nome, on_message_callback=wrapper)
        self.channel.start_consuming()
