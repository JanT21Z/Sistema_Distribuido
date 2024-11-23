FROM python:3.10-slim
WORKDIR /app
COPY consumidor.py .
RUN pip install pika
CMD ["python", "consumidor.py"]
