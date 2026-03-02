# MLflow tracking server con soporte S3/MinIO como artifact store
# Base: python slim para imagen liviana
FROM python:3.11-slim

# boto3: necesario para que MLflow acceda a MinIO (S3-compatible)
# psycopg2-binary: backend store en PostgreSQL
RUN pip install --no-cache-dir \
    mlflow>=2.13 \
    boto3>=1.34 \
    psycopg2-binary>=2.9

# Puerto estándar de MLflow UI
EXPOSE 5000

# El ENTRYPOINT se define en docker-compose via command para mayor flexibilidad
CMD ["mlflow", "server", "--host", "0.0.0.0", "--port", "5000"]
